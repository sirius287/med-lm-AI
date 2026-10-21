// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get analysisTitle => 'सिंथेटिक विश्लेषण कार्यक्षेत्र';

  @override
  String get analysisSyntheticNotice =>
      'केवल सिंथेटिक परीक्षण। ये नमूने और अवलोकन चिकित्सा जानकारी या प्रामाणिक प्रमाण नहीं हैं।';

  @override
  String get analysisChooseFixture => 'पंजीकृत परीक्षण नमूना चुनें';

  @override
  String get analysisStart => 'परीक्षण नमूना भेजें';

  @override
  String get analysisNewFixture => 'दूसरा नमूना चुनें';

  @override
  String get analysisObservations => 'निकाले गए मूल अवलोकन';

  @override
  String get analysisReview => 'निकाले गए पाठ की समीक्षा करें';

  @override
  String get analysisReport => 'प्रमाण पर आधारित रिपोर्ट';

  @override
  String get analysisHistory => 'मानव समीक्षा इतिहास';

  @override
  String get analysisReviewedText => 'समीक्षित प्रतिलेखन';

  @override
  String get analysisUnavailableInfo =>
      'अनुपलब्ध — कोई प्रामाणिक स्रोत नहीं जाँचा गया।';

  @override
  String get analysisUnverified =>
      'चिकित्सकीय रूप से असत्यापित। मानव समीक्षा केवल प्रतिलेखन की पुष्टि करती है।';

  @override
  String get analysisNoObservedText => 'कोई पाठ नहीं मिला';

  @override
  String get analysisUnreviewed => 'समीक्षा नहीं हुई';

  @override
  String get analysisConfirmed => 'प्रतिलेखन की पुष्टि हुई';

  @override
  String get analysisCorrected => 'सुधारा गया प्रतिलेखन';

  @override
  String get analysisConfirmText => 'समीक्षित पाठ की पुष्टि करें';

  @override
  String get analysisCorrectText => 'सुधार भेजें';

  @override
  String get analysisReject => 'इस समीक्षा को अस्वीकार करें';

  @override
  String get analysisUnresolved => 'अनसुलझा';

  @override
  String get analysisSaveUnresolved => 'अनसुलझी समीक्षा सहेजें';

  @override
  String get analysisConfirmField => 'मूल अवलोकन की हूबहू पुष्टि करें';

  @override
  String get analysisCorrection => 'सुधार (पाठ हूबहू रखें)';

  @override
  String get analysisClearValue => 'मान को स्पष्ट रूप से खाली करें';

  @override
  String get analysisOriginal => 'मूल पाठ';

  @override
  String get analysisNormalized => 'सामान्यीकृत अवलोकन';

  @override
  String get analysisAlternatives => 'विरोधी विकल्प';

  @override
  String get analysisUncalibrated =>
      'अंशांकन रहित अवलोकन स्कोर; स्वीकृति का आधार नहीं।';

  @override
  String get analysisLine => 'पर्चे की पंक्ति';

  @override
  String get analysisDisposition => 'पंक्ति का निर्णय';

  @override
  String get analysisSelectDisposition => 'हर पंक्ति के लिए निर्णय चुनें';

  @override
  String get analysisIncluded => 'समीक्षित पंक्ति शामिल करें';

  @override
  String get analysisExcluded => 'पंक्ति बाहर रखें';

  @override
  String get analysisDeadline => 'छवि की मूल समाप्ति';

  @override
  String get analysisProcessing => 'प्रसंस्करण स्थिति';

  @override
  String get analysisAvailability => 'इनपुट की उपलब्धता';

  @override
  String get analysisLoading => 'सिंथेटिक अनुरोध पर काम हो रहा है…';

  @override
  String get analysisCancel => 'विश्लेषण रद्द करें';

  @override
  String get analysisNewAttempt => 'नया निष्कर्षण प्रयास शुरू करें';

  @override
  String get analysisBack => 'अवलोकनों पर लौटें';

  @override
  String get analysisExpiredNotice =>
      'छवि की अवधि समाप्त हुई। सहेजा पाठ पढ़ा जा सकता है; नया प्रसंस्करण और समीक्षा उपलब्ध नहीं है।';

  @override
  String get analysisCancelledNotice =>
      'विश्लेषण रद्द हुआ। छवि हटाने का काम कतार में है; वास्तविक विलोपन की पुष्टि नहीं हुई है।';

  @override
  String get analysisImageUnavailable =>
      'समीक्षा छवि उपलब्ध नहीं है। विश्लेषण मिटाने तक सहेजे पाठ का अलग प्रतिधारण है।';

  @override
  String get analysisFinalNotice =>
      'समीक्षा अंतिम है और बदली या दोबारा खोली नहीं जा सकती। छवि मौजूदा सुरक्षा उपायों से हटेगी।';

  @override
  String get analysisSavedText =>
      'सहेजा प्रतिलेखन संवेदनशील है और चिकित्सा सत्यापन नहीं है।';

  @override
  String get analysisError =>
      'सिंथेटिक अनुरोध पूरा नहीं हुआ। इससे किसी चिकित्सा परिणाम का संकेत नहीं मिलता।';

  @override
  String get analysisConflict =>
      'संशोधन या सत्र से जुड़ा कार्य बदल गया। आगे बढ़ने से पहले ताज़ा करें।';

  @override
  String get analysisInvalidReview =>
      'हर आवश्यक फ़ील्ड की समीक्षा और हर पंक्ति का निर्णय करें। हूबहू पाठ की पुष्टि करें या वैध सुधार दें।';

  @override
  String get analysisUncertain =>
      'अनुरोध का परिणाम अनिश्चित है। संपादन बंद है; वही अनुरोध फिर भेजें या सहेजी स्थिति ताज़ा करें।';

  @override
  String get analysisRetrySame => 'वही अनुरोध फिर भेजें';

  @override
  String get analysisProviderDisabled =>
      'निष्कर्षण प्रदाता बंद है। कोई लाइव प्रदाता इस्तेमाल नहीं होगा।';

  @override
  String get analysisFixtureLiteral => 'हूबहू पाठ परीक्षण';

  @override
  String get analysisFixtureEmpty => 'खाली परीक्षण';

  @override
  String get analysisFixtureAmbiguous => 'अस्पष्ट परीक्षण';

  @override
  String get analysisStrip => 'सिंथेटिक स्ट्रिप';

  @override
  String get analysisBottle => 'सिंथेटिक बोतल';

  @override
  String get analysisTube => 'सिंथेटिक ट्यूब';

  @override
  String get analysisBox => 'सिंथेटिक डिब्बा';

  @override
  String get analysisPrescription => 'सिंथेटिक पर्चा';

  @override
  String get analysisQueued => 'कतार में';

  @override
  String get analysisValidating => 'इनपुट जाँचा जा रहा है';

  @override
  String get analysisExtracting => 'परीक्षण अवलोकन निकाले जा रहे हैं';

  @override
  String get analysisRetrieving => 'प्राप्त किया जा रहा है';

  @override
  String get analysisValidatingOutput => 'आउटपुट जाँचा जा रहा है';

  @override
  String get analysisCompleted => 'प्रसंस्करण पूरा हुआ';

  @override
  String get analysisFailed => 'प्रसंस्करण विफल हुआ';

  @override
  String get analysisNeedsInput => 'इनपुट आवश्यक है';

  @override
  String get analysisAvailable => 'उपलब्ध';

  @override
  String get analysisExpired => 'अवधि समाप्त';

  @override
  String get analysisGenericName => 'जेनेरिक नाम';

  @override
  String get analysisActiveIngredients => 'सक्रिय घटक';

  @override
  String get analysisStrength => 'स्ट्रेंथ';

  @override
  String get analysisDosageForm => 'दवा का रूप';

  @override
  String get analysisManufacturer => 'निर्माता';

  @override
  String get analysisCommonUses => 'सामान्य उपयोग';

  @override
  String get analysisMechanism => 'सामान्य कार्यप्रणाली';

  @override
  String get analysisCommonSideEffects => 'सामान्य दुष्प्रभाव';

  @override
  String get analysisSeriousEffects => 'गंभीर प्रतिकूल प्रभाव';

  @override
  String get analysisWarnings => 'चेतावनियाँ';

  @override
  String get analysisContraindications => 'उपयोग निषेध';

  @override
  String get analysisPrecautions => 'सावधानियाँ';

  @override
  String get analysisDrugInteractions => 'दवाओं के बीच अंतःक्रियाएँ';

  @override
  String get analysisFoodInteractions => 'खाद्य/पेय अंतःक्रियाएँ';

  @override
  String get analysisPregnancy => 'गर्भावस्था संबंधी जानकारी';

  @override
  String get analysisBreastfeeding => 'स्तनपान संबंधी जानकारी';

  @override
  String get analysisPediatric => 'बच्चों संबंधी जानकारी';

  @override
  String get analysisOlderAdult => 'वृद्धों संबंधी जानकारी';

  @override
  String get analysisKidney => 'गुर्दे संबंधी जानकारी';

  @override
  String get analysisLiver => 'यकृत संबंधी जानकारी';

  @override
  String get analysisStorage => 'भंडारण';

  @override
  String get analysisPrescriptionStatus => 'पर्चे/ओटीसी की स्थिति';

  @override
  String get analysisOther => 'अन्य महत्वपूर्ण जानकारी';

  @override
  String get analysisDose => 'खुराक';

  @override
  String get analysisFrequency => 'आवृत्ति';

  @override
  String get analysisRoute => 'देने का मार्ग';

  @override
  String get analysisDuration => 'अवधि';

  @override
  String get analysisTime => 'समय';

  @override
  String get analysisFoodInstruction => 'भोजन संबंधी निर्देश';

  @override
  String get analysisSpecialInstruction => 'विशेष निर्देश';

  @override
  String get appTitle => 'MedLM AI';

  @override
  String get home => 'होम';

  @override
  String get settings => 'सेटिंग्स';

  @override
  String get welcome => 'आपकी दवाओं का रिकॉर्ड, एक ही जगह।';

  @override
  String get intro =>
      'खुद दर्ज की गई दवाओं, समय-सारणी और खुराक के इतिहास का रिकॉर्ड रखने के लिए साइन इन करें।';

  @override
  String get comingSoon =>
      'इस पूर्वावलोकन में AI विश्लेषण, चिकित्सा छवियाँ अपलोड करना और सूचनाएँ भेजना उपलब्ध नहीं हैं।';

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
