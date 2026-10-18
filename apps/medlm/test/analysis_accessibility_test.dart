import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/analysis/analysis_report_screen.dart';
import 'package:medlm/analysis/analysis_review_screen.dart';
import 'package:medlm/analysis/generated/synthetic_fixture_catalog.dart';
import 'package:medlm/analysis/synthetic_analysis_controller.dart';
import 'package:medlm/l10n/app_localizations.dart';
import 'analysis_test_support.dart';
import 'analysis_ui_test.dart' show mountSynthetic;

void main() {
  for (final locale in ['en', 'hi', 'te']) {
    for (final brightness in Brightness.values) {
      for (final page in ['fixtures', 'review', 'prescription', 'report']) {
        testWidgets(
          '$locale $brightness $page 200% text, keyboard and semantics',
          (tester) async {
            tester.view.physicalSize = const Size(390, 844);
            tester.view.devicePixelRatio = 1;
            addTearDown(tester.view.resetPhysicalSize);
            addTearDown(tester.view.resetDevicePixelRatio);
            final semantics = tester.ensureSemantics();
            try {
              final (c, _, _) = await mountSynthetic(
                tester,
                FakeAnalysisService(),
                locale: locale,
                brightness: brightness,
                scale: 2,
              );
              if (page != 'fixtures') {
                await c.start(
                  bundledFixtures[page == 'prescription' ? 4 : 3],
                  '$locale-IN',
                );
                await c.beginReview();
                if (page == 'report') c.showReport();
                await tester.pumpAndSettle();
              }
              final s = AppLocalizations.of(
                tester.element(find.byType(Scaffold).first),
              )!;
              expect(find.text(s.analysisSyntheticNotice), findsWidgets);
              await tester.sendKeyEvent(LogicalKeyboardKey.tab);
              await tester.pump();
              expect(FocusManager.instance.primaryFocus, isNotNull);
              if (page == 'review' || page == 'prescription') {
                await tester.scrollUntilVisible(
                  find.byType(AnalysisReviewScreen),
                  250,
                  scrollable: find.byType(Scrollable).first,
                  maxScrolls: 100,
                );
                expect(find.byType(AnalysisReviewScreen), findsOneWidget);
                await tester.scrollUntilVisible(
                  find.byType(TextField).first,
                  250,
                  scrollable: find.byType(Scrollable).first,
                  maxScrolls: 100,
                );
              } else if (page == 'report') {
                await tester.scrollUntilVisible(
                  find.byType(AnalysisReportScreen),
                  250,
                  scrollable: find.byType(Scrollable).first,
                  maxScrolls: 100,
                );
                expect(find.byType(AnalysisReportScreen), findsOneWidget);
              }
              await tester.pumpAndSettle();
              expect(tester.takeException(), isNull);
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
  testWidgets(
    'desktop width supports prescription review and final action traversal',
    (tester) async {
      tester.view.physicalSize = const Size(1440, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final (c, _, _) = await mountSynthetic(tester, FakeAnalysisService());
      await c.start(bundledFixtures[4], 'en-IN');
      await c.beginReview();
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.byKey(const ValueKey('review-submit-unresolved')),
        500,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 100,
      );
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();
      expect(c.page, SyntheticPage.review);
      expect(tester.takeException(), isNull);
    },
  );
}
