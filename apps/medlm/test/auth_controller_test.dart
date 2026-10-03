import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart' show AuthException;
import 'package:medlm/auth/auth_controller.dart';
import 'package:medlm/auth/auth_service.dart';
import 'package:medlm/core/api_client.dart';

class SyntheticAuth implements AuthService {
  String? user;
  Object? failure;
  Completer<void>? pending;
  int logins = 0;
  int registrations = 0;
  int restores = 0;
  Future<void> _wait() async {
    await pending?.future;
    if (failure != null) throw failure!;
  }

  @override
  Future<void> login(String email, String password) async {
    logins++;
    await _wait();
    user = 'synthetic-user';
  }

  @override
  Future<void> register(String email, String password) async {
    registrations++;
    await _wait();
  }

  @override
  Future<void> logout() async {
    await _wait();
    user = null;
  }

  @override
  Future<String?> restoreUserId() async {
    restores++;
    await _wait();
    return user;
  }
}

void main() {
  test(
    'native SDK errors map to safe UI codes without exposing messages',
    () async {
      final service = SyntheticAuth()
        ..failure = const AuthException(
          'private provider detail',
          statusCode: '400',
        );
      final controller = AuthController(service, initialize: () async {});
      await controller.submit(
        'test@example.org',
        'synthetic-password',
        register: false,
      );
      expect(controller.errorCode, 'authentication_failed');
    },
  );
  test(
    'registration is not authentication; login needs verified restore',
    () async {
      final service = SyntheticAuth();
      final controller = AuthController(service, initialize: () async {});
      await controller.restore();
      expect(controller.status, AccountStatus.signedOut);
      await controller.submit(
        'test@example.org',
        'synthetic-password',
        register: true,
      );
      expect(controller.status, AccountStatus.checkEmail);
      expect(service.logins, 0);
      await controller.submit(
        'test@example.org',
        'synthetic-password',
        register: false,
      );
      expect(controller.status, AccountStatus.signedIn);
      await controller.logout();
      expect(controller.status, AccountStatus.signedOut);
    },
  );
  test('restoration outage locks account and retry can restore it', () async {
    final service = SyntheticAuth()..user = 'synthetic-user';
    final controller = AuthController(service, initialize: () async {});
    await controller.restore();
    expect(controller.status, AccountStatus.signedIn);
    service.failure = const ApiException(
      'private-provider-detail',
      status: 503,
    );
    await controller.restore();
    expect(controller.status, AccountStatus.unavailable);
    expect(controller.errorCode, 'unavailable');
    service.failure = null;
    await controller.restore();
    expect(controller.status, AccountStatus.signedIn);
    service.user = null;
    await controller.restore();
    expect(controller.status, AccountStatus.signedOut);
    expect(controller.errorCode, 'session_expired');
  });
  test(
    'failed logout locks UI and blocks automatic session resurrection',
    () async {
      final service = SyntheticAuth()..user = 'synthetic-user';
      final controller = AuthController(service, initialize: () async {});
      await controller.restore();
      service.failure = const ApiException('connection_failed');
      await controller.logout();
      expect(controller.status, AccountStatus.logoutUnconfirmed);
      final restores = service.restores;
      await controller.restore();
      expect(service.restores, restores);
      service.failure = null;
      await controller.logout();
      expect(controller.status, AccountStatus.signedOut);
    },
  );
  test(
    'duplicate submit is ignored and raw errors are never UI state',
    () async {
      final service = SyntheticAuth()..pending = Completer<void>();
      final controller = AuthController(service, initialize: () async {});
      final first = controller.submit(
        'a@example.org',
        'synthetic-password',
        register: false,
      );
      await Future<void>.delayed(Duration.zero);
      await controller.submit(
        'a@example.org',
        'synthetic-password',
        register: false,
      );
      expect(service.logins, 1);
      service.failure = StateError('raw private provider detail');
      service.pending!.complete();
      await first;
      expect(controller.errorCode, 'unavailable');
      expect(controller.busy, false);
    },
  );
  test('unconfigured native account does not call provider', () async {
    final service = SyntheticAuth();
    final controller = AuthController(
      service,
      available: false,
      initialize: () async {},
    );
    await controller.restore();
    await controller.submit(
      'a@example.org',
      'synthetic-password',
      register: false,
    );
    expect(controller.status, AccountStatus.unavailable);
    expect(service.restores, 0);
    expect(service.logins, 0);
  });
  test(
    'rate limiting and invalid credentials have safe distinct messages',
    () async {
      final service = SyntheticAuth();
      final controller = AuthController(service, initialize: () async {});
      for (final pair in [
        (429, 'rate_limited'),
        (401, 'authentication_failed'),
      ]) {
        service.failure = ApiException('private', status: pair.$1);
        await controller.submit(
          'a@example.org',
          'synthetic-password',
          register: false,
        );
        expect(controller.errorCode, pair.$2);
        expect(controller.status, isNot(AccountStatus.signedIn));
      }
    },
  );
}
