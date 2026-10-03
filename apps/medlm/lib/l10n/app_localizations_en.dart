// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'MedLM AI';

  @override
  String get home => 'Home';

  @override
  String get settings => 'Settings';

  @override
  String get welcome => 'Your medicine information, in one place.';

  @override
  String get intro =>
      'A thoughtful space for medicine information and medication reminders.';

  @override
  String get comingSoon => 'Medicine tools are coming in a later update.';

  @override
  String get theme => 'Appearance';

  @override
  String get system => 'Use device setting';

  @override
  String get light => 'Light';

  @override
  String get dark => 'Dark';

  @override
  String get language => 'Language';

  @override
  String get starting => 'Opening your workspace…';

  @override
  String get startupFailed => 'Unable to open the app. Please try again.';

  @override
  String get retry => 'Try again';

  @override
  String get notFound => 'Page not found';

  @override
  String get checkConnection => 'Check connection';

  @override
  String get connected => 'Connected';

  @override
  String get connectionFailed => 'Unable to connect. Please try again.';

  @override
  String get account => 'Account';

  @override
  String get signIn => 'Sign in';

  @override
  String get signOut => 'Sign out';

  @override
  String get createAccount => 'Create account';

  @override
  String get useExistingAccount => 'Use an existing account';

  @override
  String get email => 'Email';

  @override
  String get password => 'Password';

  @override
  String get emailInvalid => 'Enter a valid email address.';

  @override
  String get passwordRule => 'Use 12–128 characters.';

  @override
  String get showPassword => 'Show password';

  @override
  String get hidePassword => 'Hide password';

  @override
  String get signedIn => 'Signed in';

  @override
  String get sessionVerified => 'Your session has been verified for this app.';

  @override
  String get authScope =>
      'Medical uploads and analysis are not available in this version.';

  @override
  String get authWorking => 'Checking your account…';

  @override
  String get authFailed =>
      'Unable to sign in. Check your details and try again.';

  @override
  String get authRateLimited => 'Too many attempts. Please try again later.';

  @override
  String get registrationFailed =>
      'Unable to create an account. Check your details and try again.';

  @override
  String get remoteLogoutUnconfirmed =>
      'You are signed out on this device. Server sign-out could not be confirmed; the previous server session may still exist. You can sign in again.';

  @override
  String get authUnavailable =>
      'Account service is unavailable. Please try again.';

  @override
  String get authNotConfigured =>
      'Sign-in is not configured on this device yet.';

  @override
  String get sessionUnavailable =>
      'We could not verify your session. Account access remains locked until you retry successfully.';

  @override
  String get logoutUnconfirmed =>
      'Sign-out could not be confirmed. Account access is locked. Retry to confirm sign-out; a server session may still exist.';

  @override
  String get checkEmail =>
      'If registration is accepted, follow any confirmation instructions sent to your email, then sign in. Registration alone does not verify a session.';

  @override
  String get sessionExpired =>
      'Your session has ended. Sign in again to continue.';
}
