import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/app/providers.dart';
import 'package:medlm/auth/auth_controller.dart';
import 'package:medlm/design_system/theme.dart';
import 'package:medlm/l10n/app_localizations.dart';
import 'package:medlm/medications/medication_form_screen.dart';
import 'package:medlm/medications/medication_providers.dart';
import 'auth_controller_test.dart' show SyntheticAuth;
import 'manual_test_support.dart';

void main() {
  for (final locale in ['en', 'hi', 'te']) {
    for (final brightness in Brightness.values) {
      testWidgets(
        '$locale $brightness form supports 200% text keyboard and semantics',
        (tester) async {
          tester.view.physicalSize = const Size(390, 844);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          final semantics = tester.ensureSemantics();
          try {
            await tester.pumpWidget(
              ProviderScope(
                overrides: [
                  accountProvider.overrideWith(
                    (ref) => AuthController(
                      SyntheticAuth()..user = 'synthetic-user',
                      initialize: () async {},
                    ),
                  ),
                  medicationServiceProvider.overrideWithValue(
                    SyntheticMedications(),
                  ),
                ],
                child: MaterialApp(
                  theme: MedlmTheme.create(brightness),
                  locale: Locale(locale, 'IN'),
                  localizationsDelegates:
                      AppLocalizations.localizationsDelegates,
                  supportedLocales: AppLocalizations.supportedLocales,
                  builder: (context, child) => MediaQuery(
                    data: MediaQuery.of(
                      context,
                    ).copyWith(textScaler: const TextScaler.linear(2)),
                    child: child!,
                  ),
                  home: const Scaffold(body: MedicationFormScreen()),
                ),
              ),
            );
            await tester.pumpAndSettle();
            final s = AppLocalizations.of(
              tester.element(find.byType(MedicationFormScreen)),
            )!;
            await tester.scrollUntilVisible(
              find.text(s.medicineName),
              150,
              scrollable: find.byType(Scrollable).first,
            );
            expect(find.text(s.medicineName), findsOneWidget);
            await tester.sendKeyEvent(LogicalKeyboardKey.tab);
            await tester.pump();
            expect(FocusManager.instance.primaryFocus, isNotNull);
            await tester.ensureVisible(find.text(s.saveAndPreview));
            await tester.pumpAndSettle();
            expect(tester.takeException(), isNull);
            expect(
              tester.getSemantics(find.text(s.saveAndPreview)).label,
              contains(s.saveAndPreview),
            );
            await expectLater(
              tester,
              meetsGuideline(androidTapTargetGuideline),
            );
          } finally {
            semantics.dispose();
          }
        },
      );
    }
  }
}
