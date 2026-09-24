import 'dart:developer' as developer;

/// Fixed event names only: never log user content, exceptions, URLs or tokens.
abstract final class AppLog {
  static void startupFailed() => developer.log('startup_failed', name: 'medlm');
  static void requestFailed() => developer.log('request_failed', name: 'medlm');
  static void frameworkError() =>
      developer.log('framework_error', name: 'medlm');
}
