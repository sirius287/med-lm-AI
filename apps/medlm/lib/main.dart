import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app/app.dart';
import 'core/logging.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  FlutterError.onError = (_) => AppLog.frameworkError();
  PlatformDispatcher.instance.onError = (_, _) {
    AppLog.frameworkError();
    return true;
  };
  runApp(const ProviderScope(child: MedlmApp()));
}
