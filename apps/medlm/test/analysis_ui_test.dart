import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/app/app.dart';
import 'package:medlm/app/providers.dart';
import 'package:medlm/auth/auth_controller.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/analysis/analysis_report_screen.dart';
import 'package:medlm/analysis/analysis_review_screen.dart';
import 'package:medlm/analysis/fixture_selection_screen.dart';
import 'package:medlm/analysis/generated/analysis_models.dart';
import 'package:medlm/analysis/generated/synthetic_fixture_catalog.dart';
import 'package:medlm/analysis/synthetic_analysis_controller.dart';
import 'package:medlm/analysis/synthetic_analysis_harness.dart';
import 'package:medlm/analysis/synthetic_analysis_providers.dart';
import 'package:medlm/design_system/theme.dart';
import 'package:medlm/l10n/app_localizations.dart';
import 'package:medlm/medications/medication_providers.dart';
import 'analysis_test_support.dart';
import 'auth_controller_test.dart' show SyntheticAuth;
import 'manual_test_support.dart';

Future<(SyntheticAnalysisController, AuthController, SyntheticAuth)>
mountSynthetic(
  WidgetTester tester,
  FakeAnalysisService service, {
  String locale = 'en',
  Brightness brightness = Brightness.light,
  double scale = 1,
}) async {
  final auth = SyntheticAuth()..user = 'synthetic-owner';
  final account = AuthController(auth, initialize: () async {});
  await account.restore();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [accountProvider.overrideWith((ref) => account)],
      child: MaterialApp(
        theme: MedlmTheme.create(brightness),
        locale: Locale(locale, 'IN'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(scale)),
          child: child!,
        ),
        home: SyntheticAnalysisHarness(service: service),
      ),
    ),
  );
  await tester.pumpAndSettle();
  final screen = tester.widget<FixtureSelectionScreen>(
    find.byType(FixtureSelectionScreen),
  );
  return (screen.controller, account, auth);
}

Future<void> tapSynthetic(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    300,
    scrollable: find.byType(Scrollable).first,
    maxScrolls: 100,
  );
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void resumeSynthetic(WidgetTester tester) {
  for (final state in [
    AppLifecycleState.inactive,
    AppLifecycleState.hidden,
    AppLifecycleState.paused,
    AppLifecycleState.hidden,
    AppLifecycleState.inactive,
    AppLifecycleState.resumed,
  ]) {
    tester.binding.handleAppLifecycleStateChanged(state);
  }
}

void main() {
  testWidgets(
    'delayed same-owner resume preserves unsent correction and workflow',
    (tester) async {
      final service = FakeAnalysisService();
      final (c, account, auth) = await mountSynthetic(tester, service);
      await c.start(bundledFixtures[3], 'en-IN');
      await c.beginReview();
      c.correctField('medicine', '  UNSENT RESUME TEXT  ');
      await tester.pumpAndSettle();
      final wait = Completer<void>();
      auth.pending = wait;
      resumeSynthetic(tester);
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(account.busy, isTrue);
      expect(find.byType(AnalysisReviewScreen), findsNothing);
      expect(find.textContaining('UNSENT RESUME TEXT'), findsNothing);
      expect(c.analysis!.id, analysisId);
      expect(c.fields['medicine']!.reviewedValue, '  UNSENT RESUME TEXT  ');
      expect(c.canEditReview, isFalse);
      await c.submitReview('correct');
      expect(service.bodies, isEmpty);
      auth.pending = null;
      wait.complete();
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<AnalysisReviewScreen>(find.byType(AnalysisReviewScreen))
            .controller,
        same(c),
      );
      expect(c.canEditReview, isTrue);
      expect(c.analysis!.id, analysisId);
      final editor = tester.widget<TextField>(
        find.byKey(const ValueKey('correction-medicine')),
      );
      expect(editor.controller!.text, '  UNSENT RESUME TEXT  ');
    },
  );
  testWidgets(
    'delayed same-owner resume preserves the frozen replay body and key',
    (tester) async {
      final service = FakeAnalysisService();
      final (c, _, auth) = await mountSynthetic(tester, service);
      await c.start(bundledFixtures[4], 'en-IN');
      await c.beginReview();
      for (final key in c.fields.keys) {
        c.confirmField(key);
      }
      c.correctField('$firstLineId.medicine', '  FROZEN CORRECTION  ');
      c.disposition(firstLineId, 'included');
      c.disposition(secondLineId, 'excluded');
      service.loseReviewReceipt = true;
      await c.submitReview('unresolved');
      await tester.pumpAndSettle();
      final wait = Completer<void>();
      auth.pending = wait;
      resumeSynthetic(tester);
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(c.analysis!.id, analysisId);
      expect(c.uncertain, isTrue);
      await c.retryPending();
      expect(service.bodies.length, 1);
      expect(find.byType(AnalysisReviewScreen), findsNothing);
      auth.pending = null;
      wait.complete();
      await tester.pumpAndSettle();
      await c.retryPending();
      await tester.pumpAndSettle();
      expect(service.bodies.length, 2);
      expect(service.bodies[0], service.bodies[1]);
      expect(service.requestKeys['submit']!.toSet().length, 1);
      expect(service.receipts.length, 1);
      expect(
        c.fields['$firstLineId.medicine']!.reviewedValue,
        '  FROZEN CORRECTION  ',
      );
      expect(c.dispositions, {
        firstLineId: 'included',
        secondLineId: 'excluded',
      });
      expect(c.report!.acceptedTranscription, isEmpty);
    },
  );
  for (final outcome in ['logout', 'expiry', 'outage']) {
    testWidgets(
      '$outcome clears corrections and pending replay without resurrection',
      (tester) async {
        final service = FakeAnalysisService();
        final (c, account, auth) = await mountSynthetic(tester, service);
        await c.start(bundledFixtures[3], 'en-IN');
        await c.beginReview();
        c.correctField('medicine', '  OWNER PRIVATE TEXT  ');
        service.loseReviewReceipt = true;
        await c.submitReview('unresolved');
        await tester.pumpAndSettle();
        if (outcome == 'logout') {
          await account.logout();
        } else {
          auth.failure = ApiException(
            'invalid_session',
            status: outcome == 'expiry' ? 401 : 503,
          );
          await account.restore();
        }
        await tester.pumpAndSettle();
        expect(c.analysis, isNull);
        expect(c.report, isNull);
        expect(c.fields, isEmpty);
        expect(c.uncertain, isFalse);
        expect(find.byType(AnalysisReviewScreen), findsNothing);
        await c.retryPending();
        expect(service.bodies.length, 1);
        auth.failure = null;
        auth.user = 'synthetic-owner';
        await account.restore();
        await tester.pumpAndSettle();
        expect(find.byType(FixtureSelectionScreen), findsOneWidget);
        expect(find.textContaining('OWNER PRIVATE TEXT'), findsNothing);
      },
    );
  }
  testWidgets(
    'owner switch during revalidation fences a late extraction response',
    (tester) async {
      final service = FakeAnalysisService();
      final (old, account, auth) = await mountSynthetic(tester, service);
      final extraction = Completer<void>();
      service.extracting = extraction;
      final starting = old.start(bundledFixtures[3], 'en-IN');
      await tester.pump();
      final restoring = Completer<void>();
      auth.pending = restoring;
      final revalidation = account.restore();
      await tester.pump();
      auth.user = 'new-owner';
      auth.pending = null;
      restoring.complete();
      await revalidation;
      await tester.pumpAndSettle();
      final fresh = tester
          .widget<FixtureSelectionScreen>(find.byType(FixtureSelectionScreen))
          .controller;
      expect(fresh, isNot(same(old)));
      extraction.complete();
      await starting;
      await tester.pumpAndSettle();
      expect(old.analysis, isNull);
      expect(fresh.analysis, isNull);
      expect(fresh.report, isNull);
      expect(find.text(' TEST ITEM A '), findsNothing);
    },
  );
  for (final (status, code) in [
    (409, 'stale_version'),
    (410, 'analysis_expired'),
    (503, 'connection_failed'),
  ]) {
    testWidgets('missing review context exposes accessible $code recovery', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final semantics = tester.ensureSemantics();
      try {
        final service = FakeAnalysisService();
        final (c, _, _) = await mountSynthetic(tester, service, scale: 2);
        await c.start(bundledFixtures[3], 'en-IN');
        await c.beginReview();
        for (final key in c.fields.keys) {
          c.confirmField(key);
        }
        if (status == 503) {
          service.failures['report'] = ApiException(code, status: status);
          await c.refresh();
        } else {
          service.failures['submit'] = ApiException(code, status: status);
          await c.submitReview('confirm');
        }
        await tester.pumpAndSettle();
        expect(c.review, isNull);
        expect(find.byType(ReviewFieldEditor), findsNothing);
        expect(
          find.byKey(const ValueKey('review-submit-confirm')),
          findsNothing,
        );
        final error = find.byKey(const Key('review-recovery-error'));
        await tester.scrollUntilVisible(
          error,
          250,
          scrollable: find.byType(Scrollable).first,
          maxScrolls: 100,
        );
        await tester.pumpAndSettle();
        final s = AppLocalizations.of(
          tester.element(find.byType(Scaffold).first),
        )!;
        final expected = status == 410
            ? s.analysisExpiredNotice
            : status == 409
            ? s.analysisConflict
            : s.analysisError;
        expect(find.text(expected), findsOneWidget);
        expect(tester.widget<Semantics>(error).properties.liveRegion, isTrue);
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        if (status == 410) {
          service.currentStatus['availability'] = 'expired';
          service.currentReport['expired'] = true;
          service.currentReport['image_available'] = false;
          service.currentContext['image_available'] = false;
        }
        await tapSynthetic(tester, find.byKey(const Key('review-reload')));
        expect(c.needsRefresh, isFalse);
        expect(c.canEditReview, status != 410);
        expect(service.bodies, isEmpty);
        if (status != 410) {
          service.failures['report'] = const ApiException(
            'connection_failed',
            status: 503,
          );
          await c.refresh();
          await tester.pumpAndSettle();
          await tapSynthetic(tester, find.byKey(const Key('review-overview')));
          expect(c.page, SyntheticPage.observations);
        }
        expect(tester.takeException(), isNull);
      } finally {
        semantics.dispose();
      }
    });
  }
  testWidgets(
    'fixture UI to explicit field review to null/unverified 24-field report',
    (tester) async {
      final service = FakeAnalysisService();
      final (c, _, _) = await mountSynthetic(tester, service);
      await tapSynthetic(
        tester,
        find.byKey(const ValueKey('fixture-synthetic_box_literal')),
      );
      expect(service.bodies, isEmpty);
      expect(c.report!.reviewState, 'unreviewed');
      await tapSynthetic(tester, find.byKey(const Key('analysis-review')));
      expect(find.byType(AnalysisReviewScreen), findsOneWidget);
      for (final key in medicineObservationKeys) {
        await tapSynthetic(tester, find.byKey(ValueKey('confirm-$key')));
      }
      await tapSynthetic(
        tester,
        find.byKey(const ValueKey('review-submit-confirm')),
      );
      expect(find.byType(AnalysisReportScreen), findsOneWidget);
      expect(c.report!.verificationStatus, 'unverified');
      expect(c.report!.verifiedAt, isNull);
      for (final key in medicalInformationKeys) {
        expect(find.byKey(ValueKey('report-field-$key')), findsOneWidget);
      }
      expect(
        c.report!.fields.values.every((field) => field.value == null),
        isTrue,
      );
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'typing a correction preserves whitespace and explicit null is separate',
    (tester) async {
      final service = FakeAnalysisService();
      final (c, _, _) = await mountSynthetic(tester, service);
      await c.start(bundledFixtures[3], 'en-IN');
      await c.beginReview();
      await tester.pumpAndSettle();
      final correction = find.byKey(const ValueKey('correction-medicine'));
      await tester.ensureVisible(correction);
      await tester.enterText(correction, '  USER TEST TEXT  ');
      await tester.pump();
      expect(c.fields['medicine']!.reviewedValue, '  USER TEST TEXT  ');
      expect(
        c.report!.observations.medicine!.medicine.rawText,
        ' TEST ITEM A ',
      );
      await tester.enterText(correction, '');
      await tester.pump();
      expect(c.fields['medicine']!.status, 'unresolved');
      expect(c.error, 'invalid_review');
      final clear = find.descendant(
        of: find.byType(ReviewFieldEditor).first,
        matching: find.byType(CheckboxListTile),
      );
      await tester.ensureVisible(clear);
      await tester.tap(clear);
      await tester.pump();
      expect(c.fields['medicine']!.status, 'corrected');
      expect(c.fields['medicine']!.reviewedValue, isNull);
    },
  );
  testWidgets('ambiguous fixture keeps alternatives visible and unreviewed', (
    tester,
  ) async {
    final (c, _, _) = await mountSynthetic(tester, FakeAnalysisService());
    await c.start(
      bundledFixtures.firstWhere((f) => f.id == 'synthetic_box_ambiguous'),
      'en-IN',
    );
    await tester.pumpAndSettle();
    expect(find.text('TEST ITEM B'), findsOneWidget);
    expect(c.report!.acceptedTranscription, isEmpty);
    expect(c.report!.reviewState, 'unreviewed');
  });
  testWidgets(
    'empty extraction exposes needs_input without a review or report',
    (tester) async {
      final (c, _, _) = await mountSynthetic(
        tester,
        FakeAnalysisService()..extractionState = 'needs_input',
      );
      await c.start(
        bundledFixtures.firstWhere((f) => f.id == 'synthetic_box_empty'),
        'en-IN',
      );
      await tester.pumpAndSettle();
      expect(c.analysis!.job.state, 'needs_input');
      expect(find.byKey(const Key('analysis-review')), findsNothing);
      expect(find.byKey(const Key('analysis-report')), findsNothing);
    },
  );
  testWidgets(
    'loading can be cancelled and late extraction cannot restore observations',
    (tester) async {
      final wait = Completer<void>();
      final service = FakeAnalysisService()..extracting = wait;
      final (c, _, _) = await mountSynthetic(tester, service);
      await tester.tap(
        find.byKey(const ValueKey('fixture-synthetic_box_literal')),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      await tester.tap(find.byKey(const Key('analysis-cancel')));
      await tester.pumpAndSettle();
      wait.complete();
      await tester.pumpAndSettle();
      expect(c.analysis!.availability, 'cancelled');
      expect(c.observations, isNull);
      expect(
        find.textContaining('does not confirm physical deletion'),
        findsOneWidget,
      );
    },
  );
  testWidgets(
    'account switch discards prior owner text and requires a fresh fixture workflow',
    (tester) async {
      final service = FakeAnalysisService();
      final (old, account, auth) = await mountSynthetic(tester, service);
      await old.start(bundledFixtures[3], 'en-IN');
      await tester.pumpAndSettle();
      auth.user = 'second-owner';
      await account.restore();
      await tester.pumpAndSettle();
      expect(old.report, isNull);
      expect(old.analysis, isNull);
      expect(find.byType(FixtureSelectionScreen), findsOneWidget);
      expect(find.text(' TEST ITEM A '), findsNothing);
    },
  );
  testWidgets(
    'saved report stays readable after expiry but review writes remain disabled',
    (tester) async {
      final service = FakeAnalysisService();
      final (c, _, _) = await mountSynthetic(tester, service);
      await c.start(bundledFixtures[3], 'en-IN');
      await c.beginReview();
      service.currentStatus['availability'] = 'expired';
      service.currentReport['expired'] = true;
      service.currentReport['image_available'] = false;
      service.currentContext['image_available'] = false;
      await c.refresh();
      c.showReport();
      await tester.pumpAndSettle();
      expect(find.byType(AnalysisReportScreen), findsOneWidget);
      expect(c.canEditReview, isFalse);
      expect(find.textContaining('Image expired.'), findsOneWidget);
      expect(find.byKey(const Key('analysis-cancel')), findsNothing);
    },
  );
  testWidgets(
    'normal app has no synthetic navigation and deep links remain unavailable',
    (tester) async {
      final account = AuthController(
        SyntheticAuth()..user = 'normal-owner',
        initialize: () async {},
      );
      await account.restore();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            accountProvider.overrideWith((ref) => account),
            startupProvider.overrideWith((ref) async {}),
            medicationServiceProvider.overrideWithValue(SyntheticMedications()),
          ],
          child: const MedlmApp(),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(SyntheticAnalysisHarness), findsNothing);
      final container = ProviderScope.containerOf(
        tester.element(find.byType(MedlmApp)),
      );
      expect(
        () => container.read(syntheticAnalysisServiceProvider),
        throwsStateError,
      );
      container.read(routerProvider).go('/analyses');
      await tester.pumpAndSettle();
      expect(find.text('Page not found'), findsOneWidget);
      expect(find.byType(FixtureSelectionScreen), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets('expired session hides and clears prior owner observations', (
    tester,
  ) async {
    final service = FakeAnalysisService();
    final (c, _, _) = await mountSynthetic(tester, service);
    await c.start(bundledFixtures[3], 'en-IN');
    await tester.pumpAndSettle();
    service.failures['status'] = const ApiException(
      'invalid_session',
      status: 401,
    );
    await c.refresh();
    await tester.pumpAndSettle();
    expect(c.observations, isNull);
    expect(find.text(' TEST ITEM A '), findsNothing);
    expect(
      find.text('Your session has ended. Sign in again to continue.'),
      findsOneWidget,
    );
  });
  testWidgets(
    'uncertain final review exposes safe same-request replay beside final controls',
    (tester) async {
      final service = FakeAnalysisService();
      final (c, _, _) = await mountSynthetic(tester, service);
      await c.start(bundledFixtures[3], 'en-IN');
      await c.beginReview();
      for (final key in c.fields.keys) {
        c.confirmField(key);
      }
      service.loseReviewReceipt = true;
      await c.submitReview('confirm');
      await tester.pumpAndSettle();
      await tapSynthetic(tester, find.byKey(const Key('review-replay')));
      expect(service.receipts.length, 1);
      expect(c.review!.closed, isTrue);
      expect(find.byType(AnalysisReportScreen), findsOneWidget);
    },
  );
}
