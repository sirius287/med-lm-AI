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
      'इस संस्करण में चिकित्सा दस्तावेज़ अपलोड और विश्लेषण उपलब्ध नहीं हैं।';

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
}
