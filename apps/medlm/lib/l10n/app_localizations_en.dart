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
      'Sign in to manage your manually entered medications. Medical-image processing remains unavailable.';

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

  @override
  String get medications => 'Medications';

  @override
  String get todayDoses => 'Today’s doses';

  @override
  String get doseHistory => 'Dose history';

  @override
  String get addMedication => 'Add medication';

  @override
  String get editMedication => 'Edit medication';

  @override
  String get medicineName => 'Medicine name';

  @override
  String get strengthText => 'Strength (optional)';

  @override
  String get doseText => 'Dosage / instructions you were given';

  @override
  String get routeText => 'Route (optional)';

  @override
  String get additionalInstructions => 'Additional instructions (optional)';

  @override
  String get manualNotice =>
      'Manually entered · medically unverified. Enter your own instructions. This app does not recommend doses.';

  @override
  String get onlineNotice => 'Online only. No notifications are sent.';

  @override
  String get scheduleLabel => 'Schedule';

  @override
  String get dailyTimes => 'Daily at selected times';

  @override
  String get selectedWeekdays => 'Selected weekdays';

  @override
  String get fixedInterval => 'Explicit interval in hours';

  @override
  String get oneTime => 'One time';

  @override
  String get timeZone => 'Schedule timezone (IANA name)';

  @override
  String get clockTimes => 'Local times, HH:mm, separated by commas';

  @override
  String get weekdaysInput => 'Weekdays: Mon=0 … Sun=6, separated by commas';

  @override
  String get intervalHours => 'Interval hours (entered explicitly)';

  @override
  String get anchorInstant =>
      'First instant: YYYY-MM-DDTHH:mm:ss+05:30 (explicit offset)';

  @override
  String get startDate => 'Start date (YYYY-MM-DD)';

  @override
  String get endDate => 'End date (YYYY-MM-DD)';

  @override
  String get openEnded => 'I explicitly choose no end date';

  @override
  String get saveAndPreview => 'Save instructions and preview schedule';

  @override
  String get schedulePreview => 'Review upcoming doses';

  @override
  String get activateSchedule => 'Confirm and activate schedule';

  @override
  String get savedNoSchedule => 'Medication saved. Schedule is not active yet.';

  @override
  String get dstNotice =>
      'Timezone changes require review. For daylight-saving gaps use the next valid time; repeated times occur once.';

  @override
  String get taken => 'Taken';

  @override
  String get skipped => 'Skipped';

  @override
  String get pending => 'Unrecorded';

  @override
  String get cancelled => 'Cancelled';

  @override
  String get correctDose => 'Correct recorded action';

  @override
  String get corrected => 'Correction';

  @override
  String get removeMedication => 'Remove medication';

  @override
  String get removeNotice =>
      'Remove this app record and cancel future doses. This does not advise stopping your medicine. History is kept unless you choose erasure.';

  @override
  String get eraseHistory =>
      'Also erase this medication and its dose history from the active database';

  @override
  String get cancelAction => 'Cancel';

  @override
  String get confirmAction => 'Confirm';

  @override
  String get noMedications => 'No medications added yet.';

  @override
  String get noDoses => 'No scheduled doses for this day.';

  @override
  String get noHistory => 'No recorded actions in this date range.';

  @override
  String get refreshData => 'Refresh';

  @override
  String get manualError =>
      'Could not complete this action. Check your connection and entries, then retry.';

  @override
  String get manualConflict =>
      'This record changed or the preview expired. Reload and review before trying again.';

  @override
  String get requiredField => 'Enter a valid value.';

  @override
  String get viewHistory => 'View history';

  @override
  String get applyDates => 'Apply date range (up to 90 days)';

  @override
  String get indiaDisplayZone =>
      'Today and history use Asia/Kolkata. Schedule timezones stay as entered.';

  @override
  String get scheduleActive => 'Schedule active';

  @override
  String get saveUncertain =>
      'The save result is uncertain. Reload this record before editing again.';

  @override
  String get includeRemoved => 'Include removed records';

  @override
  String get removedRecord => 'Removed; history retained';
}
