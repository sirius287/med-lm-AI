import 'package:flutter/foundation.dart';

class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    this.environment = 'development',
    this.supabaseUrl = '',
    this.supabasePublishableKey = '',
  });
  factory AppConfig.fromEnvironment() {
    const supplied = String.fromEnvironment('API_BASE_URL');
    const environment = String.fromEnvironment(
      'APP_ENV',
      defaultValue: 'development',
    );
    final base = supplied.isNotEmpty
        ? supplied
        : kIsWeb
        ? Uri.base.resolve('/api/v1').toString()
        : 'http://10.0.2.2:8000/api/v1';
    final uri = Uri.parse(base);
    if (!uri.hasAuthority ||
        !['http', 'https'].contains(uri.scheme) ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (environment == 'production' && uri.scheme != 'https')) {
      throw StateError('Invalid API configuration');
    }
    return AppConfig(
      apiBaseUrl: base.replaceFirst(RegExp(r'/$'), ''),
      environment: environment,
      supabaseUrl: const String.fromEnvironment('SUPABASE_URL'),
      supabasePublishableKey: const String.fromEnvironment(
        'SUPABASE_PUBLISHABLE_KEY',
      ),
    );
  }
  final String apiBaseUrl;
  final String environment;
  final String supabaseUrl;
  final String supabasePublishableKey;
  bool get authConfigured =>
      supabaseUrl.isNotEmpty && supabasePublishableKey.isNotEmpty;
}
