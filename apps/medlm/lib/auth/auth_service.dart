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
  NativeAuthService(this.api, this.config);
  final ApiClient api;
  final AppConfig config;
  GoTrueClient get _auth {
    if (!config.authConfigured) throw const ApiException('auth_not_configured');
    return Supabase.instance.client.auth;
  }

  @override
  Future<void> register(String email, String password) async {
    await _auth.signUp(email: email, password: password);
  }

  @override
  Future<void> login(String email, String password) async {
    await _auth.signInWithPassword(email: email, password: password);
    await api.request('GET', '/auth/session', authenticated: true);
  }

  @override
  Future<String?> restoreUserId() async {
    if (!config.authConfigured || _auth.currentSession == null) return null;
    return (await api.request(
          'GET',
          '/auth/session',
          authenticated: true,
        ))['user_id']
        as String?;
  }

  @override
  Future<void> logout() async {
    try {
      await api.request('DELETE', '/auth/session', authenticated: true);
    } finally {
      await _auth.signOut(scope: SignOutScope.local);
      await const SecureSessionStorage().removePersistedSession();
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
    await api.request('DELETE', '/auth/session', authenticated: true);
    api.csrfToken = null;
  }
}
