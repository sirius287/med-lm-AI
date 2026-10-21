// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get analysisTitle => 'Synthetic analysis workspace';

  @override
  String get analysisSyntheticNotice =>
      'SYNTHETIC TEST ONLY. These fixtures and observations are not medical information or authoritative evidence.';

  @override
  String get analysisChooseFixture => 'Choose a registered test fixture';

  @override
  String get analysisStart => 'Submit test fixture';

  @override
  String get analysisNewFixture => 'Choose another fixture';

  @override
  String get analysisObservations => 'Original extracted observations';

  @override
  String get analysisReview => 'Review extracted text';

  @override
  String get analysisReport => 'Evidence-gated report';

  @override
  String get analysisHistory => 'Human review history';

  @override
  String get analysisReviewedText => 'Reviewed transcription';

  @override
  String get analysisUnavailableInfo =>
      'Unavailable — no authoritative source checked.';

  @override
  String get analysisUnverified =>
      'Medically unverified. Human review confirms transcription only.';

  @override
  String get analysisNoObservedText => 'No text observed';

  @override
  String get analysisUnreviewed => 'Unreviewed';

  @override
  String get analysisConfirmed => 'Confirmed transcription';

  @override
  String get analysisCorrected => 'Corrected transcription';

  @override
  String get analysisConfirmText => 'Confirm reviewed text';

  @override
  String get analysisCorrectText => 'Submit corrections';

  @override
  String get analysisReject => 'Reject this review';

  @override
  String get analysisUnresolved => 'Unresolved';

  @override
  String get analysisSaveUnresolved => 'Save unresolved review';

  @override
  String get analysisConfirmField => 'Confirm literal observation';

  @override
  String get analysisCorrection => 'Correction (preserve exact text)';

  @override
  String get analysisClearValue => 'Explicitly clear the value';

  @override
  String get analysisOriginal => 'Original text';

  @override
  String get analysisNormalized => 'Normalized observation';

  @override
  String get analysisAlternatives => 'Conflicting alternatives';

  @override
  String get analysisUncalibrated =>
      'Uncalibrated observation score; not an acceptance criterion.';

  @override
  String get analysisLine => 'Prescription line';

  @override
  String get analysisDisposition => 'Line disposition';

  @override
  String get analysisSelectDisposition => 'Choose a disposition for every line';

  @override
  String get analysisIncluded => 'Include reviewed line';

  @override
  String get analysisExcluded => 'Exclude line';

  @override
  String get analysisDeadline => 'Original image expiry';

  @override
  String get analysisProcessing => 'Processing state';

  @override
  String get analysisAvailability => 'Input availability';

  @override
  String get analysisLoading => 'Working on the synthetic request…';

  @override
  String get analysisCancel => 'Cancel analysis';

  @override
  String get analysisNewAttempt => 'Start a new extraction attempt';

  @override
  String get analysisBack => 'Back to observations';

  @override
  String get analysisExpiredNotice =>
      'Image expired. Saved text may remain readable; new processing and review are unavailable.';

  @override
  String get analysisCancelledNotice =>
      'Analysis cancelled. Image deletion is queued; this does not confirm physical deletion.';

  @override
  String get analysisImageUnavailable =>
      'Review image unavailable. Saved text has separate retention until analysis erasure.';

  @override
  String get analysisFinalNotice =>
      'Review is final and cannot be edited or reopened. Image deletion uses the existing safeguards.';

  @override
  String get analysisSavedText =>
      'Saved transcription remains sensitive and is not medical verification.';

  @override
  String get analysisError =>
      'Unable to complete the synthetic request. No medical result is implied.';

  @override
  String get analysisConflict =>
      'The revision or session-bound job changed. Refresh before continuing.';

  @override
  String get analysisInvalidReview =>
      'Review every required field and choose every line disposition. Confirm exact text or enter a valid correction.';

  @override
  String get analysisUncertain =>
      'The request outcome is uncertain. Editing is locked; retry the same request or refresh its saved state.';

  @override
  String get analysisRetrySame => 'Retry the same request';

  @override
  String get analysisProviderDisabled =>
      'Extraction provider is disabled. No live provider will be used.';

  @override
  String get analysisFixtureLiteral => 'Literal test';

  @override
  String get analysisFixtureEmpty => 'Empty test';

  @override
  String get analysisFixtureAmbiguous => 'Ambiguous test';

  @override
  String get analysisStrip => 'Synthetic strip';

  @override
  String get analysisBottle => 'Synthetic bottle';

  @override
  String get analysisTube => 'Synthetic tube';

  @override
  String get analysisBox => 'Synthetic box';

  @override
  String get analysisPrescription => 'Synthetic prescription';

  @override
  String get analysisQueued => 'Queued';

  @override
  String get analysisValidating => 'Validating input';

  @override
  String get analysisExtracting => 'Extracting test observations';

  @override
  String get analysisRetrieving => 'Retrieving';

  @override
  String get analysisValidatingOutput => 'Validating output';

  @override
  String get analysisCompleted => 'Processing completed';

  @override
  String get analysisFailed => 'Processing failed';

  @override
  String get analysisNeedsInput => 'Input required';

  @override
  String get analysisAvailable => 'Available';

  @override
  String get analysisExpired => 'Expired';

  @override
  String get analysisGenericName => 'Generic name';

  @override
  String get analysisActiveIngredients => 'Active ingredients';

  @override
  String get analysisStrength => 'Strength';

  @override
  String get analysisDosageForm => 'Dosage form';

  @override
  String get analysisManufacturer => 'Manufacturer';

  @override
  String get analysisCommonUses => 'Common uses';

  @override
  String get analysisMechanism => 'General mechanism/action';

  @override
  String get analysisCommonSideEffects => 'Common side effects';

  @override
  String get analysisSeriousEffects => 'Serious adverse effects';

  @override
  String get analysisWarnings => 'Warnings';

  @override
  String get analysisContraindications => 'Contraindications';

  @override
  String get analysisPrecautions => 'Precautions';

  @override
  String get analysisDrugInteractions => 'Drug interactions';

  @override
  String get analysisFoodInteractions => 'Food/beverage interactions';

  @override
  String get analysisPregnancy => 'Pregnancy considerations';

  @override
  String get analysisBreastfeeding => 'Breastfeeding considerations';

  @override
  String get analysisPediatric => 'Pediatric considerations';

  @override
  String get analysisOlderAdult => 'Older-adult considerations';

  @override
  String get analysisKidney => 'Kidney considerations';

  @override
  String get analysisLiver => 'Liver considerations';

  @override
  String get analysisStorage => 'Storage';

  @override
  String get analysisPrescriptionStatus => 'Prescription/OTC status';

  @override
  String get analysisOther => 'Other important information';

  @override
  String get analysisDose => 'Dose';

  @override
  String get analysisFrequency => 'Frequency';

  @override
  String get analysisRoute => 'Route';

  @override
  String get analysisDuration => 'Duration';

  @override
  String get analysisTime => 'Time';

  @override
  String get analysisFoodInstruction => 'Food instructions';

  @override
  String get analysisSpecialInstruction => 'Special instructions';

  @override
  String get appTitle => 'MedLM AI';

  @override
  String get home => 'Home';

  @override
  String get settings => 'Settings';

  @override
  String get welcome => 'Your medication log, in one place.';

  @override
  String get intro =>
      'Sign in to track manually entered medications, schedules and dose history.';

  @override
  String get comingSoon =>
      'AI analysis, medical-image uploads and notification delivery are unavailable in this preview.';

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
