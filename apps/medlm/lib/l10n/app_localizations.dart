import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_hi.dart';
import 'app_localizations_te.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('hi'),
    Locale('te'),
  ];

  /// No description provided for @analysisTitle.
  ///
  /// In en, this message translates to:
  /// **'Synthetic analysis workspace'**
  String get analysisTitle;

  /// No description provided for @analysisSyntheticNotice.
  ///
  /// In en, this message translates to:
  /// **'SYNTHETIC TEST ONLY. These fixtures and observations are not medical information or authoritative evidence.'**
  String get analysisSyntheticNotice;

  /// No description provided for @analysisChooseFixture.
  ///
  /// In en, this message translates to:
  /// **'Choose a registered test fixture'**
  String get analysisChooseFixture;

  /// No description provided for @analysisStart.
  ///
  /// In en, this message translates to:
  /// **'Submit test fixture'**
  String get analysisStart;

  /// No description provided for @analysisNewFixture.
  ///
  /// In en, this message translates to:
  /// **'Choose another fixture'**
  String get analysisNewFixture;

  /// No description provided for @analysisObservations.
  ///
  /// In en, this message translates to:
  /// **'Original extracted observations'**
  String get analysisObservations;

  /// No description provided for @analysisReview.
  ///
  /// In en, this message translates to:
  /// **'Review extracted text'**
  String get analysisReview;

  /// No description provided for @analysisReport.
  ///
  /// In en, this message translates to:
  /// **'Evidence-gated report'**
  String get analysisReport;

  /// No description provided for @analysisHistory.
  ///
  /// In en, this message translates to:
  /// **'Human review history'**
  String get analysisHistory;

  /// No description provided for @analysisReviewedText.
  ///
  /// In en, this message translates to:
  /// **'Reviewed transcription'**
  String get analysisReviewedText;

  /// No description provided for @analysisUnavailableInfo.
  ///
  /// In en, this message translates to:
  /// **'Unavailable — no authoritative source checked.'**
  String get analysisUnavailableInfo;

  /// No description provided for @analysisUnverified.
  ///
  /// In en, this message translates to:
  /// **'Medically unverified. Human review confirms transcription only.'**
  String get analysisUnverified;

  /// No description provided for @analysisNoObservedText.
  ///
  /// In en, this message translates to:
  /// **'No text observed'**
  String get analysisNoObservedText;

  /// No description provided for @analysisUnreviewed.
  ///
  /// In en, this message translates to:
  /// **'Unreviewed'**
  String get analysisUnreviewed;

  /// No description provided for @analysisConfirmed.
  ///
  /// In en, this message translates to:
  /// **'Confirmed transcription'**
  String get analysisConfirmed;

  /// No description provided for @analysisCorrected.
  ///
  /// In en, this message translates to:
  /// **'Corrected transcription'**
  String get analysisCorrected;

  /// No description provided for @analysisConfirmText.
  ///
  /// In en, this message translates to:
  /// **'Confirm reviewed text'**
  String get analysisConfirmText;

  /// No description provided for @analysisCorrectText.
  ///
  /// In en, this message translates to:
  /// **'Submit corrections'**
  String get analysisCorrectText;

  /// No description provided for @analysisReject.
  ///
  /// In en, this message translates to:
  /// **'Reject this review'**
  String get analysisReject;

  /// No description provided for @analysisUnresolved.
  ///
  /// In en, this message translates to:
  /// **'Unresolved'**
  String get analysisUnresolved;

  /// No description provided for @analysisSaveUnresolved.
  ///
  /// In en, this message translates to:
  /// **'Save unresolved review'**
  String get analysisSaveUnresolved;

  /// No description provided for @analysisConfirmField.
  ///
  /// In en, this message translates to:
  /// **'Confirm literal observation'**
  String get analysisConfirmField;

  /// No description provided for @analysisCorrection.
  ///
  /// In en, this message translates to:
  /// **'Correction (preserve exact text)'**
  String get analysisCorrection;

  /// No description provided for @analysisClearValue.
  ///
  /// In en, this message translates to:
  /// **'Explicitly clear the value'**
  String get analysisClearValue;

  /// No description provided for @analysisOriginal.
  ///
  /// In en, this message translates to:
  /// **'Original text'**
  String get analysisOriginal;

  /// No description provided for @analysisNormalized.
  ///
  /// In en, this message translates to:
  /// **'Normalized observation'**
  String get analysisNormalized;

  /// No description provided for @analysisAlternatives.
  ///
  /// In en, this message translates to:
  /// **'Conflicting alternatives'**
  String get analysisAlternatives;

  /// No description provided for @analysisUncalibrated.
  ///
  /// In en, this message translates to:
  /// **'Uncalibrated observation score; not an acceptance criterion.'**
  String get analysisUncalibrated;

  /// No description provided for @analysisLine.
  ///
  /// In en, this message translates to:
  /// **'Prescription line'**
  String get analysisLine;

  /// No description provided for @analysisDisposition.
  ///
  /// In en, this message translates to:
  /// **'Line disposition'**
  String get analysisDisposition;

  /// No description provided for @analysisSelectDisposition.
  ///
  /// In en, this message translates to:
  /// **'Choose a disposition for every line'**
  String get analysisSelectDisposition;

  /// No description provided for @analysisIncluded.
  ///
  /// In en, this message translates to:
  /// **'Include reviewed line'**
  String get analysisIncluded;

  /// No description provided for @analysisExcluded.
  ///
  /// In en, this message translates to:
  /// **'Exclude line'**
  String get analysisExcluded;

  /// No description provided for @analysisDeadline.
  ///
  /// In en, this message translates to:
  /// **'Original image expiry'**
  String get analysisDeadline;

  /// No description provided for @analysisProcessing.
  ///
  /// In en, this message translates to:
  /// **'Processing state'**
  String get analysisProcessing;

  /// No description provided for @analysisAvailability.
  ///
  /// In en, this message translates to:
  /// **'Input availability'**
  String get analysisAvailability;

  /// No description provided for @analysisLoading.
  ///
  /// In en, this message translates to:
  /// **'Working on the synthetic request…'**
  String get analysisLoading;

  /// No description provided for @analysisCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel analysis'**
  String get analysisCancel;

  /// No description provided for @analysisNewAttempt.
  ///
  /// In en, this message translates to:
  /// **'Start a new extraction attempt'**
  String get analysisNewAttempt;

  /// No description provided for @analysisBack.
  ///
  /// In en, this message translates to:
  /// **'Back to observations'**
  String get analysisBack;

  /// No description provided for @analysisExpiredNotice.
  ///
  /// In en, this message translates to:
  /// **'Image expired. Saved text may remain readable; new processing and review are unavailable.'**
  String get analysisExpiredNotice;

  /// No description provided for @analysisCancelledNotice.
  ///
  /// In en, this message translates to:
  /// **'Analysis cancelled. Image deletion is queued; this does not confirm physical deletion.'**
  String get analysisCancelledNotice;

  /// No description provided for @analysisImageUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Review image unavailable. Saved text has separate retention until analysis erasure.'**
  String get analysisImageUnavailable;

  /// No description provided for @analysisFinalNotice.
  ///
  /// In en, this message translates to:
  /// **'Review is final and cannot be edited or reopened. Image deletion uses the existing safeguards.'**
  String get analysisFinalNotice;

  /// No description provided for @analysisSavedText.
  ///
  /// In en, this message translates to:
  /// **'Saved transcription remains sensitive and is not medical verification.'**
  String get analysisSavedText;

  /// No description provided for @analysisError.
  ///
  /// In en, this message translates to:
  /// **'Unable to complete the synthetic request. No medical result is implied.'**
  String get analysisError;

  /// No description provided for @analysisConflict.
  ///
  /// In en, this message translates to:
  /// **'The revision or session-bound job changed. Refresh before continuing.'**
  String get analysisConflict;

  /// No description provided for @analysisInvalidReview.
  ///
  /// In en, this message translates to:
  /// **'Review every required field and choose every line disposition. Confirm exact text or enter a valid correction.'**
  String get analysisInvalidReview;

  /// No description provided for @analysisUncertain.
  ///
  /// In en, this message translates to:
  /// **'The request outcome is uncertain. Editing is locked; retry the same request or refresh its saved state.'**
  String get analysisUncertain;

  /// No description provided for @analysisRetrySame.
  ///
  /// In en, this message translates to:
  /// **'Retry the same request'**
  String get analysisRetrySame;

  /// No description provided for @analysisProviderDisabled.
  ///
  /// In en, this message translates to:
  /// **'Extraction provider is disabled. No live provider will be used.'**
  String get analysisProviderDisabled;

  /// No description provided for @analysisFixtureLiteral.
  ///
  /// In en, this message translates to:
  /// **'Literal test'**
  String get analysisFixtureLiteral;

  /// No description provided for @analysisFixtureEmpty.
  ///
  /// In en, this message translates to:
  /// **'Empty test'**
  String get analysisFixtureEmpty;

  /// No description provided for @analysisFixtureAmbiguous.
  ///
  /// In en, this message translates to:
  /// **'Ambiguous test'**
  String get analysisFixtureAmbiguous;

  /// No description provided for @analysisStrip.
  ///
  /// In en, this message translates to:
  /// **'Synthetic strip'**
  String get analysisStrip;

  /// No description provided for @analysisBottle.
  ///
  /// In en, this message translates to:
  /// **'Synthetic bottle'**
  String get analysisBottle;

  /// No description provided for @analysisTube.
  ///
  /// In en, this message translates to:
  /// **'Synthetic tube'**
  String get analysisTube;

  /// No description provided for @analysisBox.
  ///
  /// In en, this message translates to:
  /// **'Synthetic box'**
  String get analysisBox;

  /// No description provided for @analysisPrescription.
  ///
  /// In en, this message translates to:
  /// **'Synthetic prescription'**
  String get analysisPrescription;

  /// No description provided for @analysisQueued.
  ///
  /// In en, this message translates to:
  /// **'Queued'**
  String get analysisQueued;

  /// No description provided for @analysisValidating.
  ///
  /// In en, this message translates to:
  /// **'Validating input'**
  String get analysisValidating;

  /// No description provided for @analysisExtracting.
  ///
  /// In en, this message translates to:
  /// **'Extracting test observations'**
  String get analysisExtracting;

  /// No description provided for @analysisRetrieving.
  ///
  /// In en, this message translates to:
  /// **'Retrieving'**
  String get analysisRetrieving;

  /// No description provided for @analysisValidatingOutput.
  ///
  /// In en, this message translates to:
  /// **'Validating output'**
  String get analysisValidatingOutput;

  /// No description provided for @analysisCompleted.
  ///
  /// In en, this message translates to:
  /// **'Processing completed'**
  String get analysisCompleted;

  /// No description provided for @analysisFailed.
  ///
  /// In en, this message translates to:
  /// **'Processing failed'**
  String get analysisFailed;

  /// No description provided for @analysisNeedsInput.
  ///
  /// In en, this message translates to:
  /// **'Input required'**
  String get analysisNeedsInput;

  /// No description provided for @analysisAvailable.
  ///
  /// In en, this message translates to:
  /// **'Available'**
  String get analysisAvailable;

  /// No description provided for @analysisExpired.
  ///
  /// In en, this message translates to:
  /// **'Expired'**
  String get analysisExpired;

  /// No description provided for @analysisGenericName.
  ///
  /// In en, this message translates to:
  /// **'Generic name'**
  String get analysisGenericName;

  /// No description provided for @analysisActiveIngredients.
  ///
  /// In en, this message translates to:
  /// **'Active ingredients'**
  String get analysisActiveIngredients;

  /// No description provided for @analysisStrength.
  ///
  /// In en, this message translates to:
  /// **'Strength'**
  String get analysisStrength;

  /// No description provided for @analysisDosageForm.
  ///
  /// In en, this message translates to:
  /// **'Dosage form'**
  String get analysisDosageForm;

  /// No description provided for @analysisManufacturer.
  ///
  /// In en, this message translates to:
  /// **'Manufacturer'**
  String get analysisManufacturer;

  /// No description provided for @analysisCommonUses.
  ///
  /// In en, this message translates to:
  /// **'Common uses'**
  String get analysisCommonUses;

  /// No description provided for @analysisMechanism.
  ///
  /// In en, this message translates to:
  /// **'General mechanism/action'**
  String get analysisMechanism;

  /// No description provided for @analysisCommonSideEffects.
  ///
  /// In en, this message translates to:
  /// **'Common side effects'**
  String get analysisCommonSideEffects;

  /// No description provided for @analysisSeriousEffects.
  ///
  /// In en, this message translates to:
  /// **'Serious adverse effects'**
  String get analysisSeriousEffects;

  /// No description provided for @analysisWarnings.
  ///
  /// In en, this message translates to:
  /// **'Warnings'**
  String get analysisWarnings;

  /// No description provided for @analysisContraindications.
  ///
  /// In en, this message translates to:
  /// **'Contraindications'**
  String get analysisContraindications;

  /// No description provided for @analysisPrecautions.
  ///
  /// In en, this message translates to:
  /// **'Precautions'**
  String get analysisPrecautions;

  /// No description provided for @analysisDrugInteractions.
  ///
  /// In en, this message translates to:
  /// **'Drug interactions'**
  String get analysisDrugInteractions;

  /// No description provided for @analysisFoodInteractions.
  ///
  /// In en, this message translates to:
  /// **'Food/beverage interactions'**
  String get analysisFoodInteractions;

  /// No description provided for @analysisPregnancy.
  ///
  /// In en, this message translates to:
  /// **'Pregnancy considerations'**
  String get analysisPregnancy;

  /// No description provided for @analysisBreastfeeding.
  ///
  /// In en, this message translates to:
  /// **'Breastfeeding considerations'**
  String get analysisBreastfeeding;

  /// No description provided for @analysisPediatric.
  ///
  /// In en, this message translates to:
  /// **'Pediatric considerations'**
  String get analysisPediatric;

  /// No description provided for @analysisOlderAdult.
  ///
  /// In en, this message translates to:
  /// **'Older-adult considerations'**
  String get analysisOlderAdult;

  /// No description provided for @analysisKidney.
  ///
  /// In en, this message translates to:
  /// **'Kidney considerations'**
  String get analysisKidney;

  /// No description provided for @analysisLiver.
  ///
  /// In en, this message translates to:
  /// **'Liver considerations'**
  String get analysisLiver;

  /// No description provided for @analysisStorage.
  ///
  /// In en, this message translates to:
  /// **'Storage'**
  String get analysisStorage;

  /// No description provided for @analysisPrescriptionStatus.
  ///
  /// In en, this message translates to:
  /// **'Prescription/OTC status'**
  String get analysisPrescriptionStatus;

  /// No description provided for @analysisOther.
  ///
  /// In en, this message translates to:
  /// **'Other important information'**
  String get analysisOther;

  /// No description provided for @analysisDose.
  ///
  /// In en, this message translates to:
  /// **'Dose'**
  String get analysisDose;

  /// No description provided for @analysisFrequency.
  ///
  /// In en, this message translates to:
  /// **'Frequency'**
  String get analysisFrequency;

  /// No description provided for @analysisRoute.
  ///
  /// In en, this message translates to:
  /// **'Route'**
  String get analysisRoute;

  /// No description provided for @analysisDuration.
  ///
  /// In en, this message translates to:
  /// **'Duration'**
  String get analysisDuration;

  /// No description provided for @analysisTime.
  ///
  /// In en, this message translates to:
  /// **'Time'**
  String get analysisTime;

  /// No description provided for @analysisFoodInstruction.
  ///
  /// In en, this message translates to:
  /// **'Food instructions'**
  String get analysisFoodInstruction;

  /// No description provided for @analysisSpecialInstruction.
  ///
  /// In en, this message translates to:
  /// **'Special instructions'**
  String get analysisSpecialInstruction;

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'MedLM AI'**
  String get appTitle;

  /// No description provided for @home.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get home;

  /// No description provided for @settings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// No description provided for @welcome.
  ///
  /// In en, this message translates to:
  /// **'Your medicine information, in one place.'**
  String get welcome;

  /// No description provided for @intro.
  ///
  /// In en, this message translates to:
  /// **'A thoughtful space for medicine information and medication reminders.'**
  String get intro;

  /// No description provided for @comingSoon.
  ///
  /// In en, this message translates to:
  /// **'Medicine tools are coming in a later update.'**
  String get comingSoon;

  /// No description provided for @theme.
  ///
  /// In en, this message translates to:
  /// **'Appearance'**
  String get theme;

  /// No description provided for @system.
  ///
  /// In en, this message translates to:
  /// **'Use device setting'**
  String get system;

  /// No description provided for @light.
  ///
  /// In en, this message translates to:
  /// **'Light'**
  String get light;

  /// No description provided for @dark.
  ///
  /// In en, this message translates to:
  /// **'Dark'**
  String get dark;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @starting.
  ///
  /// In en, this message translates to:
  /// **'Opening your workspace…'**
  String get starting;

  /// No description provided for @startupFailed.
  ///
  /// In en, this message translates to:
  /// **'Unable to open the app. Please try again.'**
  String get startupFailed;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get retry;

  /// No description provided for @notFound.
  ///
  /// In en, this message translates to:
  /// **'Page not found'**
  String get notFound;

  /// No description provided for @checkConnection.
  ///
  /// In en, this message translates to:
  /// **'Check connection'**
  String get checkConnection;

  /// No description provided for @connected.
  ///
  /// In en, this message translates to:
  /// **'Connected'**
  String get connected;

  /// No description provided for @connectionFailed.
  ///
  /// In en, this message translates to:
  /// **'Unable to connect. Please try again.'**
  String get connectionFailed;

  /// No description provided for @account.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get account;

  /// No description provided for @signIn.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get signIn;

  /// No description provided for @signOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get signOut;

  /// No description provided for @createAccount.
  ///
  /// In en, this message translates to:
  /// **'Create account'**
  String get createAccount;

  /// No description provided for @useExistingAccount.
  ///
  /// In en, this message translates to:
  /// **'Use an existing account'**
  String get useExistingAccount;

  /// No description provided for @email.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get email;

  /// No description provided for @password.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get password;

  /// No description provided for @emailInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid email address.'**
  String get emailInvalid;

  /// No description provided for @passwordRule.
  ///
  /// In en, this message translates to:
  /// **'Use 12–128 characters.'**
  String get passwordRule;

  /// No description provided for @showPassword.
  ///
  /// In en, this message translates to:
  /// **'Show password'**
  String get showPassword;

  /// No description provided for @hidePassword.
  ///
  /// In en, this message translates to:
  /// **'Hide password'**
  String get hidePassword;

  /// No description provided for @signedIn.
  ///
  /// In en, this message translates to:
  /// **'Signed in'**
  String get signedIn;

  /// No description provided for @sessionVerified.
  ///
  /// In en, this message translates to:
  /// **'Your session has been verified for this app.'**
  String get sessionVerified;

  /// No description provided for @authScope.
  ///
  /// In en, this message translates to:
  /// **'Sign in to manage your manually entered medications. Medical-image processing remains unavailable.'**
  String get authScope;

  /// No description provided for @authWorking.
  ///
  /// In en, this message translates to:
  /// **'Checking your account…'**
  String get authWorking;

  /// No description provided for @authFailed.
  ///
  /// In en, this message translates to:
  /// **'Unable to sign in. Check your details and try again.'**
  String get authFailed;

  /// No description provided for @authRateLimited.
  ///
  /// In en, this message translates to:
  /// **'Too many attempts. Please try again later.'**
  String get authRateLimited;

  /// No description provided for @registrationFailed.
  ///
  /// In en, this message translates to:
  /// **'Unable to create an account. Check your details and try again.'**
  String get registrationFailed;

  /// No description provided for @remoteLogoutUnconfirmed.
  ///
  /// In en, this message translates to:
  /// **'You are signed out on this device. Server sign-out could not be confirmed; the previous server session may still exist. You can sign in again.'**
  String get remoteLogoutUnconfirmed;

  /// No description provided for @authUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Account service is unavailable. Please try again.'**
  String get authUnavailable;

  /// No description provided for @authNotConfigured.
  ///
  /// In en, this message translates to:
  /// **'Sign-in is not configured on this device yet.'**
  String get authNotConfigured;

  /// No description provided for @sessionUnavailable.
  ///
  /// In en, this message translates to:
  /// **'We could not verify your session. Account access remains locked until you retry successfully.'**
  String get sessionUnavailable;

  /// No description provided for @logoutUnconfirmed.
  ///
  /// In en, this message translates to:
  /// **'Sign-out could not be confirmed. Account access is locked. Retry to confirm sign-out; a server session may still exist.'**
  String get logoutUnconfirmed;

  /// No description provided for @checkEmail.
  ///
  /// In en, this message translates to:
  /// **'If registration is accepted, follow any confirmation instructions sent to your email, then sign in. Registration alone does not verify a session.'**
  String get checkEmail;

  /// No description provided for @sessionExpired.
  ///
  /// In en, this message translates to:
  /// **'Your session has ended. Sign in again to continue.'**
  String get sessionExpired;

  /// No description provided for @medications.
  ///
  /// In en, this message translates to:
  /// **'Medications'**
  String get medications;

  /// No description provided for @todayDoses.
  ///
  /// In en, this message translates to:
  /// **'Today’s doses'**
  String get todayDoses;

  /// No description provided for @doseHistory.
  ///
  /// In en, this message translates to:
  /// **'Dose history'**
  String get doseHistory;

  /// No description provided for @addMedication.
  ///
  /// In en, this message translates to:
  /// **'Add medication'**
  String get addMedication;

  /// No description provided for @editMedication.
  ///
  /// In en, this message translates to:
  /// **'Edit medication'**
  String get editMedication;

  /// No description provided for @medicineName.
  ///
  /// In en, this message translates to:
  /// **'Medicine name'**
  String get medicineName;

  /// No description provided for @strengthText.
  ///
  /// In en, this message translates to:
  /// **'Strength (optional)'**
  String get strengthText;

  /// No description provided for @doseText.
  ///
  /// In en, this message translates to:
  /// **'Dosage / instructions you were given'**
  String get doseText;

  /// No description provided for @routeText.
  ///
  /// In en, this message translates to:
  /// **'Route (optional)'**
  String get routeText;

  /// No description provided for @additionalInstructions.
  ///
  /// In en, this message translates to:
  /// **'Additional instructions (optional)'**
  String get additionalInstructions;

  /// No description provided for @manualNotice.
  ///
  /// In en, this message translates to:
  /// **'Manually entered · medically unverified. Enter your own instructions. This app does not recommend doses.'**
  String get manualNotice;

  /// No description provided for @onlineNotice.
  ///
  /// In en, this message translates to:
  /// **'Online only. No notifications are sent.'**
  String get onlineNotice;

  /// No description provided for @scheduleLabel.
  ///
  /// In en, this message translates to:
  /// **'Schedule'**
  String get scheduleLabel;

  /// No description provided for @dailyTimes.
  ///
  /// In en, this message translates to:
  /// **'Daily at selected times'**
  String get dailyTimes;

  /// No description provided for @selectedWeekdays.
  ///
  /// In en, this message translates to:
  /// **'Selected weekdays'**
  String get selectedWeekdays;

  /// No description provided for @fixedInterval.
  ///
  /// In en, this message translates to:
  /// **'Explicit interval in hours'**
  String get fixedInterval;

  /// No description provided for @oneTime.
  ///
  /// In en, this message translates to:
  /// **'One time'**
  String get oneTime;

  /// No description provided for @timeZone.
  ///
  /// In en, this message translates to:
  /// **'Schedule timezone (IANA name)'**
  String get timeZone;

  /// No description provided for @clockTimes.
  ///
  /// In en, this message translates to:
  /// **'Local times, HH:mm, separated by commas'**
  String get clockTimes;

  /// No description provided for @weekdaysInput.
  ///
  /// In en, this message translates to:
  /// **'Weekdays: Mon=0 … Sun=6, separated by commas'**
  String get weekdaysInput;

  /// No description provided for @intervalHours.
  ///
  /// In en, this message translates to:
  /// **'Interval hours (entered explicitly)'**
  String get intervalHours;

  /// No description provided for @anchorInstant.
  ///
  /// In en, this message translates to:
  /// **'First instant: YYYY-MM-DDTHH:mm:ss+05:30 (explicit offset)'**
  String get anchorInstant;

  /// No description provided for @startDate.
  ///
  /// In en, this message translates to:
  /// **'Start date (YYYY-MM-DD)'**
  String get startDate;

  /// No description provided for @endDate.
  ///
  /// In en, this message translates to:
  /// **'End date (YYYY-MM-DD)'**
  String get endDate;

  /// No description provided for @openEnded.
  ///
  /// In en, this message translates to:
  /// **'I explicitly choose no end date'**
  String get openEnded;

  /// No description provided for @saveAndPreview.
  ///
  /// In en, this message translates to:
  /// **'Save instructions and preview schedule'**
  String get saveAndPreview;

  /// No description provided for @schedulePreview.
  ///
  /// In en, this message translates to:
  /// **'Review upcoming doses'**
  String get schedulePreview;

  /// No description provided for @activateSchedule.
  ///
  /// In en, this message translates to:
  /// **'Confirm and activate schedule'**
  String get activateSchedule;

  /// No description provided for @savedNoSchedule.
  ///
  /// In en, this message translates to:
  /// **'Medication saved. Schedule is not active yet.'**
  String get savedNoSchedule;

  /// No description provided for @dstNotice.
  ///
  /// In en, this message translates to:
  /// **'Timezone changes require review. For daylight-saving gaps use the next valid time; repeated times occur once.'**
  String get dstNotice;

  /// No description provided for @taken.
  ///
  /// In en, this message translates to:
  /// **'Taken'**
  String get taken;

  /// No description provided for @skipped.
  ///
  /// In en, this message translates to:
  /// **'Skipped'**
  String get skipped;

  /// No description provided for @pending.
  ///
  /// In en, this message translates to:
  /// **'Unrecorded'**
  String get pending;

  /// No description provided for @cancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get cancelled;

  /// No description provided for @correctDose.
  ///
  /// In en, this message translates to:
  /// **'Correct recorded action'**
  String get correctDose;

  /// No description provided for @corrected.
  ///
  /// In en, this message translates to:
  /// **'Correction'**
  String get corrected;

  /// No description provided for @removeMedication.
  ///
  /// In en, this message translates to:
  /// **'Remove medication'**
  String get removeMedication;

  /// No description provided for @removeNotice.
  ///
  /// In en, this message translates to:
  /// **'Remove this app record and cancel future doses. This does not advise stopping your medicine. History is kept unless you choose erasure.'**
  String get removeNotice;

  /// No description provided for @eraseHistory.
  ///
  /// In en, this message translates to:
  /// **'Also erase this medication and its dose history from the active database'**
  String get eraseHistory;

  /// No description provided for @cancelAction.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancelAction;

  /// No description provided for @confirmAction.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirmAction;

  /// No description provided for @noMedications.
  ///
  /// In en, this message translates to:
  /// **'No medications added yet.'**
  String get noMedications;

  /// No description provided for @noDoses.
  ///
  /// In en, this message translates to:
  /// **'No scheduled doses for this day.'**
  String get noDoses;

  /// No description provided for @noHistory.
  ///
  /// In en, this message translates to:
  /// **'No recorded actions in this date range.'**
  String get noHistory;

  /// No description provided for @refreshData.
  ///
  /// In en, this message translates to:
  /// **'Refresh'**
  String get refreshData;

  /// No description provided for @manualError.
  ///
  /// In en, this message translates to:
  /// **'Could not complete this action. Check your connection and entries, then retry.'**
  String get manualError;

  /// No description provided for @manualConflict.
  ///
  /// In en, this message translates to:
  /// **'This record changed or the preview expired. Reload and review before trying again.'**
  String get manualConflict;

  /// No description provided for @requiredField.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid value.'**
  String get requiredField;

  /// No description provided for @viewHistory.
  ///
  /// In en, this message translates to:
  /// **'View history'**
  String get viewHistory;

  /// No description provided for @applyDates.
  ///
  /// In en, this message translates to:
  /// **'Apply date range (up to 90 days)'**
  String get applyDates;

  /// No description provided for @indiaDisplayZone.
  ///
  /// In en, this message translates to:
  /// **'Today and history use Asia/Kolkata. Schedule timezones stay as entered.'**
  String get indiaDisplayZone;

  /// No description provided for @scheduleActive.
  ///
  /// In en, this message translates to:
  /// **'Schedule active'**
  String get scheduleActive;

  /// No description provided for @saveUncertain.
  ///
  /// In en, this message translates to:
  /// **'The save result is uncertain. Reload this record before editing again.'**
  String get saveUncertain;

  /// No description provided for @includeRemoved.
  ///
  /// In en, this message translates to:
  /// **'Include removed records'**
  String get includeRemoved;

  /// No description provided for @removedRecord.
  ///
  /// In en, this message translates to:
  /// **'Removed; history retained'**
  String get removedRecord;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'hi', 'te'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'hi':
      return AppLocalizationsHi();
    case 'te':
      return AppLocalizationsTe();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
