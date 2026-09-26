import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:medlm/auth/auth_service.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/core/config.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class TestStorage extends LocalStorage {
  bool removed = false;
  bool fail = false;
  @override
  Future<void> initialize() async {}
  @override
  Future<String?> accessToken() async => null;
  @override
  Future<bool> hasAccessToken() async => !removed;
  @override
  Future<void> persistSession(String value) async {}
  @override
  Future<void> removePersistedSession() async {
    if (fail) throw StateError('synthetic storage error');
    removed = true;
  }
}

class TestAuth implements GoTrueClient {
  bool signedOut = false;
  bool failSignOut = false;
  @override
  Session? get currentSession => signedOut
      ? null
      : Session(
          accessToken: 'synthetic-access',
          refreshToken: 'synthetic-refresh',
          tokenType: 'bearer',
          user: User(
            id: 'synthetic-user',
            appMetadata: {},
            userMetadata: {},
            aud: 'authenticated',
            createdAt: '2026-09-25T00:00:00Z',
          ),
        );
  @override
  Future<void> signOut({SignOutScope scope = SignOutScope.local}) async {
    signedOut = true;
    if (failSignOut) throw StateError('synthetic provider error');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

const config = AppConfig(
  apiBaseUrl: 'https://api.example.org/api/v1',
  supabaseUrl: 'https://auth.example.org',
  supabasePublishableKey: 'public-test',
);

void main() {
  test(
    'concurrent token requests share refresh and logout blocks late result',
    () async {
      final refresh = Completer<String?>();
      var calls = 0;
      final access = NativeTokenAccess(() {
        calls++;
        return refresh.future;
      });
      final first = access.token();
      final second = access.token();
      final cleanup = access.blockAndDrain();
      refresh.complete('synthetic-token');
      expect(await first, isNull);
      expect(await second, isNull);
      await cleanup;
      expect(calls, 1);
      expect(await access.token(), isNull);
    },
  );

  test(
    'native logout clears storage despite backend and provider failures',
    () async {
      final sdk = TestAuth()..failSignOut = true;
      final storage = TestStorage();
      final api = ApiClient(
        config.apiBaseUrl,
        MockClient(
          (_) async => http.Response(
            jsonEncode({
              'error': {'code': 'database_unavailable'},
            }),
            503,
          ),
        ),
      );
      final service = NativeAuthService(
        api,
        config,
        client: () => sdk,
        storage: storage,
      );
      await expectLater(
        service.logout(),
        throwsA(
          isA<ApiException>().having(
            (e) => e.status,
            'server revocation not confirmed',
            503,
          ),
        ),
      );
      expect(sdk.signedOut, isTrue);
      expect(storage.removed, isTrue);
    },
  );

  test(
    'native restoration clears invalid session but preserves temporary failure',
    () async {
      for (final status in [401, 503]) {
        final sdk = TestAuth();
        final storage = TestStorage();
        final api = ApiClient(
          config.apiBaseUrl,
          MockClient(
            (_) async => http.Response(
              jsonEncode({
                'error': {'code': 'synthetic_error'},
              }),
              status,
            ),
          ),
        );
        final service = NativeAuthService(
          api,
          config,
          client: () => sdk,
          storage: storage,
        );
        if (status == 401) {
          expect(await service.restoreUserId(), isNull);
          expect(storage.removed, isTrue);
        } else {
          await expectLater(
            service.restoreUserId(),
            throwsA(isA<ApiException>()),
          );
          expect(storage.removed, isFalse);
        }
      }
    },
  );

  test(
    'web CSRF persists on network failure, clears after logout or 401',
    () async {
      var status = 503;
      final api = ApiClient(
        config.apiBaseUrl,
        MockClient((request) async {
          expect(request.headers['X-CSRF-Token'], 'synthetic-csrf');
          return http.Response(
            status == 204
                ? ''
                : jsonEncode({
                    'error': {'code': 'synthetic_error'},
                  }),
            status,
          );
        }),
      )..csrfToken = 'synthetic-csrf';
      final service = WebAuthService(api);
      await expectLater(service.logout(), throwsA(isA<ApiException>()));
      expect(api.csrfToken, 'synthetic-csrf');
      status = 204;
      await service.logout();
      expect(api.csrfToken, isNull);
      api.csrfToken = 'synthetic-csrf';
      status = 401;
      expect(await service.restoreUserId(), isNull);
      expect(api.csrfToken, isNull);
    },
  );

  test(
    'storage cleanup failure is surfaced without provider details',
    () async {
      final storage = TestStorage()..fail = true;
      final api = ApiClient(
        config.apiBaseUrl,
        MockClient((_) async => http.Response('', 204)),
      );
      final service = NativeAuthService(
        api,
        config,
        client: () => TestAuth(),
        storage: storage,
      );
      await expectLater(
        service.logout(),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'safe code',
            'local_session_cleanup_failed',
          ),
        ),
      );
    },
  );
}
