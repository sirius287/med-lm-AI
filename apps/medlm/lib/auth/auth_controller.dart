import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart' show AuthException;
import '../core/api_client.dart';
import 'auth_service.dart';

enum AccountStatus {
  initial,
  signedOut,
  signedIn,
  checkEmail,
  unavailable,
  logoutUnconfirmed,
}

/// UI state only. Provider/backend adapters remain the authentication authority.
class AuthController extends ChangeNotifier {
  AuthController(
    this.service, {
    required this.initialize,
    this.available = true,
  });
  final AuthService service;
  final Future<void> Function() initialize;
  final bool available;
  AccountStatus status = AccountStatus.initial;
  bool busy = false;
  String? errorCode;
  bool _disposed = false;

  void _emit() {
    if (!_disposed) notifyListeners();
  }

  Future<void> _run(Future<void> Function() action) async {
    if (busy || _disposed) return;
    busy = true;
    errorCode = null;
    _emit();
    try {
      await initialize();
      await action();
    } on ApiException catch (error) {
      if (error.code == 'native_logout_unconfirmed') {
        status = AccountStatus.signedOut;
        errorCode = 'remote_logout_unconfirmed';
        return;
      }
      errorCode = error.status == 429
          ? 'rate_limited'
          : error.status == 401 || error.status == 422
          ? 'authentication_failed'
          : 'unavailable';
    } on AuthException catch (error) {
      errorCode = error.statusCode == '429'
          ? 'rate_limited'
          : const ['400', '401', '422'].contains(error.statusCode)
          ? 'authentication_failed'
          : 'unavailable';
    } on Object {
      // Never display raw provider exceptions, email addresses or credentials.
      errorCode = 'unavailable';
    } finally {
      busy = false;
      _emit();
    }
  }

  Future<void> restore() async {
    if (busy ||
        status == AccountStatus.logoutUnconfirmed ||
        errorCode == 'remote_logout_unconfirmed') {
      return;
    }
    if (!available) {
      status = AccountStatus.unavailable;
      _emit();
      return;
    }
    final wasSignedIn = status == AccountStatus.signedIn;
    // Hide verified UI while revalidation is in progress or fails.
    status = AccountStatus.initial;
    await _run(() async {
      status = await service.restoreUserId() == null
          ? AccountStatus.signedOut
          : AccountStatus.signedIn;
      if (wasSignedIn && status == AccountStatus.signedOut) {
        errorCode = 'session_expired';
      }
    });
    if (status == AccountStatus.initial && errorCode != null) {
      status = AccountStatus.unavailable;
      _emit();
    }
  }

  Future<void> submit(
    String email,
    String password, {
    required bool register,
  }) async {
    if (busy || !available || status == AccountStatus.logoutUnconfirmed) return;
    await _run(() async {
      if (register) {
        await service.register(email, password);
        status = AccountStatus.checkEmail;
      } else {
        await service.login(email, password);
        final user = await service.restoreUserId();
        if (user == null) {
          throw const ApiException('invalid_session', status: 401);
        }
        status = AccountStatus.signedIn;
      }
    });
  }

  Future<void> logout() async {
    if (busy) return;
    status = AccountStatus.logoutUnconfirmed;
    await _run(() async {
      await service.logout();
      status = AccountStatus.signedOut;
    });
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
