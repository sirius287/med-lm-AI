import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../core/api_client.dart';
import '../core/config.dart';

abstract interface class AuthService {
  Future<void> register(String email, String password);
  Future<void> login(String email, String password);
  Future<void> logout();
  Future<String?> restoreUserId();
}

/// Coordinates adapter requests; SDK refresh deduplication remains in place too.
class NativeTokenAccess {
  NativeTokenAccess(this.resolve);
  final Future<String?> Function() resolve;
  Future<String?>? _pending;
  bool _blocked = false;
  void enable() => _blocked = false;
  Future<String?> token() async {
    if (_blocked) return null;
    final pending = _pending ??= Future<String?>.sync(
      resolve,
    ).timeout(const Duration(seconds: 15));
    try {
      final value = await pending;
      return _blocked ? null : value;
    } on ApiException {
      rethrow;
    } on Object {
      throw const ApiException('session_refresh_failed');
    } finally {
      if (identical(_pending, pending)) _pending = null;
    }
  }

  Future<void> blockAndDrain() async {
    _blocked = true;
    try {
      await _pending;
    } on Object {
      // Cleanup proceeds even if a refresh already in flight failed.
    }
  }
}

class SecureSessionStorage extends LocalStorage {
  const SecureSessionStorage();
  static const _store = FlutterSecureStorage();
  static const _key = 'medlm_auth_session';
  @override
  Future<void> initialize() async {}
  @override
  Future<String?> accessToken() => _store.read(key: _key);
  @override
  Future<bool> hasAccessToken() => _store.containsKey(key: _key);
  @override
  Future<void> persistSession(String persistSessionString) =>
      _store.write(key: _key, value: persistSessionString);
  @override
  Future<void> removePersistedSession() => _store.delete(key: _key);
}

Future<void> initializeNativeAuth(AppConfig config) async {
  if (!kIsWeb && config.authConfigured) {
    await Supabase.initialize(
      url: config.supabaseUrl,
      publishableKey: config.supabasePublishableKey,
      authOptions: const FlutterAuthClientOptions(
        localStorage: SecureSessionStorage(),
        detectSessionInUri: false,
      ),
    );
  }
}

class NativeAuthService implements AuthService {
  NativeAuthService(
    this.api,
    this.config, {
    this.tokenAccess,
    GoTrueClient Function()? client,
    LocalStorage? storage,
  }) : _client = client ?? (() => Supabase.instance.client.auth),
       _storage = storage ?? const SecureSessionStorage();
  final ApiClient api;
  final AppConfig config;
  final NativeTokenAccess? tokenAccess;
  final GoTrueClient Function() _client;
  final LocalStorage _storage;
  bool _logoutConfirmed = false;
  GoTrueClient get _auth {
    if (!config.authConfigured) throw const ApiException('auth_not_configured');
    return _client();
  }

  @override
  Future<void> register(String email, String password) async {
    _logoutConfirmed = false;
    await _auth.signUp(email: email, password: password);
  }

  @override
  Future<void> login(String email, String password) async {
    _logoutConfirmed = false;
    await _auth.signInWithPassword(email: email, password: password);
    tokenAccess?.enable();
    try {
      await api.request('GET', '/auth/session', authenticated: true);
    } on ApiException catch (error) {
      if (error.status == 401) await _clearLocal();
      rethrow;
    }
  }

  @override
  Future<String?> restoreUserId() async {
    if (!config.authConfigured || _auth.currentSession == null) return null;
    try {
      return (await api.request(
            'GET',
            '/auth/session',
            authenticated: true,
          ))['user_id']
          as String?;
    } on ApiException catch (error) {
      if (error.status == 401) {
        await _clearLocal();
        return null;
      }
      rethrow;
    }
  }

  @override
  Future<void> logout() async {
    ApiException? failure;
    try {
      if (!_logoutConfirmed) {
        if (_auth.currentSession == null) {
          throw const ApiException('native_logout_unconfirmed');
        }
        await api.request('DELETE', '/auth/session', authenticated: true);
        _logoutConfirmed = true;
      }
    } on ApiException catch (error) {
      failure = error;
    } on Object {
      failure = const ApiException('native_logout_unconfirmed');
    } finally {
      // Cleanup failure must take precedence: never claim local sign-out then.
      await _clearLocal();
    }
    if (failure != null) {
      throw ApiException('native_logout_unconfirmed', status: failure.status);
    }
  }

  Future<void> _clearLocal() async {
    await tokenAccess?.blockAndDrain();
    api.csrfToken = null;
    try {
      await _auth
          .signOut(scope: SignOutScope.local)
          .timeout(const Duration(seconds: 10));
    } on Object {
      // SDK clears in-memory session before provider sign-out. Never expose raw errors.
    } finally {
      try {
        await _storage.removePersistedSession();
      } on Object {
        throw const ApiException('local_session_cleanup_failed');
      }
    }
  }
}

class WebAuthService implements AuthService {
  WebAuthService(this.api);
  final ApiClient api;
  @override
  Future<void> register(String email, String password) async {
    await api.request(
      'POST',
      '/auth/register',
      body: {'email': email, 'password': password},
    );
  }

  @override
  Future<void> login(String email, String password) async {
    final result = await api.request(
      'POST',
      '/auth/login',
      body: {'email': email, 'password': password},
    );
    api.csrfToken = result['csrf_token'] as String;
  }

  @override
  Future<String?> restoreUserId() async {
    try {
      final result = await api.request(
        'GET',
        '/auth/session',
        authenticated: true,
      );
      if (result['user_id'] is! String ||
          (result['user_id'] as String).isEmpty ||
          result['csrf_token'] is! String ||
          (result['csrf_token'] as String).isEmpty) {
        throw const ApiException('invalid_session_response');
      }
      api.csrfToken = result['csrf_token'] as String?;
      return result['user_id'] as String?;
    } on ApiException catch (error) {
      if (error.status == 401) {
        api.csrfToken = null;
        return null;
      }
      rethrow;
    }
  }

  @override
  Future<void> logout() async {
    // A reload/outage can leave an HttpOnly cookie without its in-memory CSRF.
    // Recover it inside logout, without restoring signed-in UI state.
    if (api.csrfToken == null) {
      final user = await restoreUserId();
      if (user == null) return; // Verified 401: no usable app session remains.
      if (api.csrfToken == null) {
        throw const ApiException('csrf_unavailable');
      }
    }
    try {
      await api.request('DELETE', '/auth/session', authenticated: true);
    } on ApiException catch (error) {
      if (error.status == 403 && error.code == 'csrf_failed') {
        api.csrfToken = null; // Next explicit retry must bootstrap again.
      }
      rethrow;
    }
    api.csrfToken = null;
  }
}
