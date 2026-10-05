// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get appTitle => 'MedLM AI';

  @override
  String get home => 'होम';

  @override
  String get settings => 'सेटिंग्स';

  @override
  String get welcome => 'आपकी दवा की जानकारी, एक ही जगह।';

  @override
  String get intro =>
      'दवा की जानकारी और दवा लेने के रिमाइंडर के लिए एक सरल स्थान।';

  @override
  String get comingSoon => 'दवा से जुड़ी सुविधाएँ अगले अपडेट में आएँगी।';

  @override
  String get theme => 'दिखावट';

  @override
  String get system => 'डिवाइस की सेटिंग';

  @override
  String get light => 'लाइट';

  @override
  String get dark => 'डार्क';

  @override
  String get language => 'भाषा';

  @override
  String get starting => 'आपका कार्यक्षेत्र खुल रहा है…';

  @override
  String get startupFailed => 'ऐप नहीं खुल पाया। कृपया फिर से कोशिश करें।';

  @override
  String get retry => 'फिर से कोशिश करें';

  @override
  String get notFound => 'पेज नहीं मिला';

  @override
  String get checkConnection => 'कनेक्शन जाँचें';

  @override
  String get connected => 'कनेक्ट हो गया';

  @override
  String get connectionFailed =>
      'कनेक्ट नहीं हो पाया। कृपया फिर से कोशिश करें।';

  @override
  String get account => 'खाता';

  @override
  String get signIn => 'साइन इन करें';

  @override
  String get signOut => 'साइन आउट करें';

  @override
  String get createAccount => 'खाता बनाएँ';

  @override
  String get useExistingAccount => 'मौजूदा खाते से साइन इन करें';

  @override
  String get email => 'ईमेल';

  @override
  String get password => 'पासवर्ड';

  @override
  String get emailInvalid => 'मान्य ईमेल पता दर्ज करें।';

  @override
  String get passwordRule => '12–128 अक्षरों का उपयोग करें।';

  @override
  String get showPassword => 'पासवर्ड दिखाएँ';

  @override
  String get hidePassword => 'पासवर्ड छिपाएँ';

  @override
  String get signedIn => 'साइन इन हो गया';

  @override
  String get sessionVerified => 'इस ऐप के लिए आपका सत्र सत्यापित किया गया है।';

  @override
  String get authScope =>
      'स्वयं दर्ज दवाएँ प्रबंधित करने के लिए साइन इन करें। चिकित्सा-चित्र विश्लेषण अभी उपलब्ध नहीं है।';

  @override
  String get authWorking => 'आपका खाता जाँचा जा रहा है…';

  @override
  String get authFailed => 'साइन इन नहीं हो सका। विवरण जाँचकर फिर प्रयास करें।';

  @override
  String get authRateLimited =>
      'बहुत अधिक प्रयास हुए हैं। कृपया बाद में फिर प्रयास करें।';

  @override
  String get registrationFailed =>
      'खाता नहीं बन सका। विवरण जाँचकर फिर प्रयास करें।';

  @override
  String get remoteLogoutUnconfirmed =>
      'इस डिवाइस पर आप साइन आउट हो गए हैं। सर्वर पर साइन आउट की पुष्टि नहीं हो सकी; पिछला सत्र अभी भी मौजूद हो सकता है। आप फिर साइन इन कर सकते हैं।';

  @override
  String get authUnavailable =>
      'खाता सेवा उपलब्ध नहीं है। कृपया फिर प्रयास करें।';

  @override
  String get authNotConfigured =>
      'इस डिवाइस पर साइन इन अभी कॉन्फ़िगर नहीं किया गया है।';

  @override
  String get sessionUnavailable =>
      'आपका सत्र सत्यापित नहीं हो सका। सफलतापूर्वक फिर प्रयास करने तक खाते की पहुँच बंद रहेगी।';

  @override
  String get logoutUnconfirmed =>
      'साइन आउट की पुष्टि नहीं हो सकी। खाते की पहुँच बंद है। पुष्टि के लिए फिर प्रयास करें; सर्वर पर सत्र अभी भी मौजूद हो सकता है।';

  @override
  String get checkEmail =>
      'पंजीकरण स्वीकार होने पर ईमेल में मिले पुष्टि निर्देशों का पालन करें, फिर साइन इन करें। केवल पंजीकरण से सत्र सत्यापित नहीं होता।';

  @override
  String get sessionExpired =>
      'आपका सत्र समाप्त हो गया है। जारी रखने के लिए फिर साइन इन करें।';

  @override
  String get medications => 'दवाएँ';

  @override
  String get todayDoses => 'आज की खुराकें';

  @override
  String get doseHistory => 'खुराक का इतिहास';

  @override
  String get addMedication => 'दवा जोड़ें';

  @override
  String get editMedication => 'दवा संपादित करें';

  @override
  String get medicineName => 'दवा का नाम';

  @override
  String get strengthText => 'दवा की शक्ति (वैकल्पिक)';

  @override
  String get doseText => 'आपको दिए गए खुराक / निर्देश';

  @override
  String get routeText => 'लेने का तरीका (वैकल्पिक)';

  @override
  String get additionalInstructions => 'अतिरिक्त निर्देश (वैकल्पिक)';

  @override
  String get manualNotice =>
      'स्वयं दर्ज किया गया · चिकित्सकीय सत्यापन नहीं हुआ। अपने निर्देश दर्ज करें। यह ऐप खुराक की सलाह नहीं देता।';

  @override
  String get onlineNotice => 'केवल ऑनलाइन। कोई सूचना नहीं भेजी जाती।';

  @override
  String get scheduleLabel => 'समय-सारणी';

  @override
  String get dailyTimes => 'प्रतिदिन चुने हुए समय पर';

  @override
  String get selectedWeekdays => 'सप्ताह के चुने हुए दिन';

  @override
  String get fixedInterval => 'घंटों में स्पष्ट अंतराल';

  @override
  String get oneTime => 'एक बार';

  @override
  String get timeZone => 'समय क्षेत्र (IANA नाम)';

  @override
  String get clockTimes => 'स्थानीय समय, HH:mm, अल्पविराम से अलग';

  @override
  String get weekdaysInput => 'दिन: सोम=0 … रवि=6, अल्पविराम से अलग';

  @override
  String get intervalHours => 'अंतराल के घंटे (स्वयं दर्ज करें)';

  @override
  String get anchorInstant =>
      'पहला समय: YYYY-MM-DDTHH:mm:ss+05:30 (स्पष्ट ऑफ़सेट)';

  @override
  String get startDate => 'आरंभ तिथि (YYYY-MM-DD)';

  @override
  String get endDate => 'अंतिम तिथि (YYYY-MM-DD)';

  @override
  String get openEnded => 'मैं स्पष्ट रूप से कोई अंतिम तिथि नहीं चुनता/चुनती';

  @override
  String get saveAndPreview => 'निर्देश सहेजें और समय-सारणी देखें';

  @override
  String get schedulePreview => 'आने वाली खुराकों की समीक्षा करें';

  @override
  String get activateSchedule => 'पुष्टि करें और समय-सारणी सक्रिय करें';

  @override
  String get savedNoSchedule => 'दवा सहेजी गई। समय-सारणी अभी सक्रिय नहीं है।';

  @override
  String get dstNotice =>
      'समय क्षेत्र बदलने पर समीक्षा आवश्यक है। घड़ी बदलने से अनुपलब्ध समय पर अगला मान्य समय लें; दोहराया समय एक बार आएगा।';

  @override
  String get taken => 'ली गई';

  @override
  String get skipped => 'छोड़ी गई';

  @override
  String get pending => 'दर्ज नहीं';

  @override
  String get cancelled => 'रद्द';

  @override
  String get correctDose => 'दर्ज कार्रवाई सुधारें';

  @override
  String get corrected => 'सुधार';

  @override
  String get removeMedication => 'दवा हटाएँ';

  @override
  String get removeNotice =>
      'यह ऐप रिकॉर्ड हटाएँ और आगे की खुराकें रद्द करें। यह दवा बंद करने की सलाह नहीं है। मिटाने का विकल्प न चुनने पर इतिहास रहेगा।';

  @override
  String get eraseHistory =>
      'सक्रिय डेटाबेस से इस दवा और खुराक इतिहास को भी मिटाएँ';

  @override
  String get cancelAction => 'रद्द करें';

  @override
  String get confirmAction => 'पुष्टि करें';

  @override
  String get noMedications => 'अभी कोई दवा नहीं जोड़ी गई।';

  @override
  String get noDoses => 'इस दिन कोई निर्धारित खुराक नहीं है।';

  @override
  String get noHistory => 'इस अवधि में कोई कार्रवाई दर्ज नहीं है।';

  @override
  String get refreshData => 'ताज़ा करें';

  @override
  String get manualError =>
      'यह कार्रवाई पूरी नहीं हुई। कनेक्शन और प्रविष्टियाँ जाँचकर पुनः प्रयास करें।';

  @override
  String get manualConflict =>
      'रिकॉर्ड बदल गया या पूर्वावलोकन की अवधि समाप्त हुई। पुनः लोड करके समीक्षा करें।';

  @override
  String get requiredField => 'मान्य मान दर्ज करें।';

  @override
  String get viewHistory => 'इतिहास देखें';

  @override
  String get applyDates => 'तिथि अवधि लागू करें (90 दिन तक)';

  @override
  String get indiaDisplayZone =>
      'आज और इतिहास Asia/Kolkata में दिखते हैं। समय-सारणी का क्षेत्र दर्ज अनुसार रहेगा।';

  @override
  String get scheduleActive => 'समय-सारणी सक्रिय';

  @override
  String get saveUncertain =>
      'सहेजने का परिणाम अनिश्चित है। फिर संपादित करने से पहले रिकॉर्ड पुनः लोड करें।';

  @override
  String get includeRemoved => 'हटाए गए रिकॉर्ड भी दिखाएँ';

  @override
  String get removedRecord => 'हटाया गया; इतिहास सुरक्षित है';
}
