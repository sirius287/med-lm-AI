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
}
