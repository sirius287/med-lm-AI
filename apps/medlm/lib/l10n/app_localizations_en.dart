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
}
