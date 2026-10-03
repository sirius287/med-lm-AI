import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:medlm/auth/auth_controller.dart';
import 'package:medlm/auth/auth_service.dart';
import 'package:medlm/core/api_client.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'auth_session_test.dart' show TestAuth, TestStorage, config;

class ReauthTestAuth extends TestAuth {
  @override
  Future<AuthResponse> signInWithPassword({
    String? email,
    String? phone,
    required String password,
    String? captchaToken,
  }) async {
    signedOut = false;
    return AuthResponse(session: currentSession);
  }
}

void main() {
  test(
    'native failed revocation clears credentials and allows honest local recovery',
    () async {
      final sdk = ReauthTestAuth();
      final storage = TestStorage();
      final access = NativeTokenAccess(
        () async => sdk.currentSession?.accessToken,
      );
      var deletes = 0;
      final api = ApiClient(
        config.apiBaseUrl,
        MockClient((request) async {
          if (request.method == 'GET') {
            return http.Response('{"user_id":"synthetic-user"}', 200);
          }
          deletes++;
          expect(request.headers['Authorization'], 'Bearer synthetic-access');
          return http.Response(
            '{"error":{"code":"database_unavailable"}}',
            503,
          );
        }),
        accessToken: access.token,
      );
      final controller = AuthController(
        NativeAuthService(
          api,
          config,
          tokenAccess: access,
          client: () => sdk,
          storage: storage,
        ),
        initialize: () async {},
      );
      await controller.restore();
      await controller.logout();
      expect(storage.removed, isTrue);
      expect(await access.token(), isNull);
      expect(controller.status, AccountStatus.signedOut);
      expect(controller.errorCode, 'remote_logout_unconfirmed');
      await controller.restore();
      expect(controller.errorCode, 'remote_logout_unconfirmed');
      await controller.logout();
      expect(deletes, 1, reason: 'Never retry revocation without credentials');
      expect(controller.status, AccountStatus.signedOut);
      await controller.submit(
        'test@example.org',
        'synthetic-password',
        register: false,
      );
      expect(controller.status, AccountStatus.signedIn);
      expect(controller.errorCode, isNull);
    },
  );

  test(
    'web outage then logout recovers CSRF without unlocking account',
    () async {
      var outage = true;
      var deletes = 0;
      late AuthController controller;
      final api = ApiClient(
        config.apiBaseUrl,
        MockClient((request) async {
          if (request.method == 'GET') {
            if (outage) {
              return http.Response('{"error":{"code":"unavailable"}}', 503);
            }
            expect(controller.status, AccountStatus.logoutUnconfirmed);
            return http.Response(
              jsonEncode({
                'user_id': 'synthetic-user',
                'csrf_token': 'synthetic-csrf',
              }),
              200,
            );
          }
          deletes++;
          if (request.headers['X-CSRF-Token'] != 'synthetic-csrf') {
            return http.Response('{"error":{"code":"csrf_failed"}}', 403);
          }
          return http.Response('', 204);
        }),
      );
      controller = AuthController(WebAuthService(api), initialize: () async {});
      await controller.restore();
      expect(controller.status, AccountStatus.unavailable);
      await controller.logout();
      expect(controller.status, AccountStatus.logoutUnconfirmed);
      outage = false;
      await controller.logout();
      expect(controller.status, AccountStatus.signedOut);
      expect(api.csrfToken, isNull);
      expect(deletes, 1, reason: 'No mutation until CSRF is restored');
    },
  );

  test(
    'native cleanup failure stays locked; retry cleans without another server request',
    () async {
      final sdk = TestAuth();
      final storage = TestStorage()..fail = true;
      var calls = 0;
      final api = ApiClient(
        config.apiBaseUrl,
        MockClient((_) async {
          calls++;
          return http.Response('', 204);
        }),
      );
      final controller = AuthController(
        NativeAuthService(api, config, client: () => sdk, storage: storage),
        initialize: () async {},
      );
      await controller.logout();
      expect(controller.status, AccountStatus.logoutUnconfirmed);
      storage.fail = false;
      await controller.logout();
      expect(controller.status, AccountStatus.signedOut);
      expect(storage.removed, isTrue);
      expect(calls, 1);
    },
  );

  test(
    'web stale CSRF remains locked then explicitly retries with fresh CSRF',
    () async {
      var deletes = 0;
      final api = ApiClient(
        config.apiBaseUrl,
        MockClient((request) async {
          if (request.method == 'GET') {
            return http.Response(
              '{"user_id":"synthetic-user","csrf_token":"fresh"}',
              200,
            );
          }
          deletes++;
          if (request.headers['X-CSRF-Token'] != 'fresh') {
            return http.Response('{"error":{"code":"csrf_failed"}}', 403);
          }
          return http.Response('', 204);
        }),
      )..csrfToken = 'stale';
      final controller = AuthController(
        WebAuthService(api),
        initialize: () async {},
      );
      await controller.logout();
      expect(controller.status, AccountStatus.logoutUnconfirmed);
      expect(api.csrfToken, isNull);
      await controller.logout();
      expect(controller.status, AccountStatus.signedOut);
      expect(deletes, 2);
    },
  );

  test(
    'web missing CSRF never mutates on invalid bootstrap; 401 permits signed-out state',
    () async {
      var status = 200;
      final api = ApiClient(
        config.apiBaseUrl,
        MockClient((request) async {
          expect(request.method, 'GET');
          return http.Response(
            status == 200
                ? '{"user_id":"synthetic-user"}'
                : '{"error":{"code":"invalid_session"}}',
            status,
          );
        }),
      );
      final controller = AuthController(
        WebAuthService(api),
        initialize: () async {},
      );
      await controller.logout();
      expect(controller.status, AccountStatus.logoutUnconfirmed);
      status = 401;
      await controller.logout();
      expect(controller.status, AccountStatus.signedOut);
    },
  );

  for (final status in [401, 503]) {
    test(
      'successful web login followed by $status verification never unlocks UI',
      () async {
        final api = ApiClient(
          config.apiBaseUrl,
          MockClient(
            (request) async => request.method == 'POST'
                ? http.Response('{"csrf_token":"synthetic-csrf"}', 200)
                : http.Response('{"error":{"code":"unavailable"}}', status),
          ),
        );
        final controller = AuthController(
          WebAuthService(api),
          initialize: () async {},
        );
        await controller.submit(
          'test@example.org',
          'synthetic-password',
          register: false,
        );
        expect(controller.status, isNot(AccountStatus.signedIn));
        expect(
          controller.errorCode,
          status == 401 ? 'authentication_failed' : 'unavailable',
        );
      },
    );
  }
}
