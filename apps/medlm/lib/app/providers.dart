import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../auth/auth_service.dart';
import '../auth/auth_controller.dart';
import '../core/api_client.dart';
import '../core/config.dart';
import '../core/http_client.dart';

final configProvider = Provider<AppConfig>(
  (ref) => AppConfig.fromEnvironment(),
);
final themeModeProvider = StateProvider<ThemeMode>((ref) => ThemeMode.system);
final localeProvider = StateProvider<Locale>((ref) => const Locale('en', 'IN'));
final startupProvider = FutureProvider<void>(
  (ref) => initializeNativeAuth(ref.read(configProvider)),
);
final nativeTokenProvider = Provider<NativeTokenAccess>((ref) {
  final config = ref.watch(configProvider);
  return NativeTokenAccess(() async {
    if (kIsWeb || !config.authConfigured) return null;
    final auth = Supabase.instance.client.auth;
    if (auth.currentSession?.isExpired ?? false) await auth.refreshSession();
    return auth.currentSession?.accessToken;
  });
});
final apiProvider = Provider<ApiClient>((ref) {
  final config = ref.watch(configProvider);
  final client = createHttpClient();
  ref.onDispose(client.close);
  return ApiClient(
    config.apiBaseUrl,
    client,
    accessToken: ref.watch(nativeTokenProvider).token,
  );
});
final authProvider = Provider<AuthService>(
  (ref) => kIsWeb
      ? WebAuthService(ref.watch(apiProvider))
      : NativeAuthService(
          ref.watch(apiProvider),
          ref.watch(configProvider),
          tokenAccess: ref.watch(nativeTokenProvider),
        ),
);

final accountProvider = ChangeNotifierProvider<AuthController>(
  (ref) => AuthController(
    ref.watch(authProvider),
    available: kIsWeb || ref.watch(configProvider).authConfigured,
    initialize: () {
      if (ref.read(startupProvider).hasError) ref.invalidate(startupProvider);
      return ref.read(startupProvider.future);
    },
  ),
);
