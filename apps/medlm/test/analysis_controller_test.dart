import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/analysis/generated/synthetic_fixture_catalog.dart';
import 'package:medlm/analysis/synthetic_analysis_controller.dart';
import 'analysis_test_support.dart';

Future<SyntheticAnalysisController> started(
  FakeAnalysisService service, {
  bool prescription = false,
}) async {
  final controller = SyntheticAnalysisController(service, () {});
  await controller.start(bundledFixtures[prescription ? 4 : 3], 'en-IN');
  return controller;
}

void confirmAll(SyntheticAnalysisController c) {
  for (final key in c.fields.keys) {
    c.confirmField(key);
  }
}

void main() {
  for (final changeRevision in [false, true]) {
    for (final operation in ['report', 'reviewContext']) {
      for (final status in [null, 503]) {
        test(
          'incomplete $operation refresh ($status, revision change $changeRevision) hides stale projections',
          () async {
            final s = FakeAnalysisService();
            final c = await started(s);
            await c.beginReview();
            c.correctField('medicine', '  UNSENT CORRECTION  ');
            final original = c.analysis;
            final revision = changeRevision ? 2 : 1;
            s.currentStatus = {
              ...s.currentStatus,
              'version': 3,
              'result_revision': revision,
            };
            s.currentReport = {
              ...s.currentReport,
              'analysis_version': 3,
              'revision': revision,
            };
            s.currentContext = {
              ...s.currentContext,
              'version': 3,
              'revision': revision,
            };
            s.failures[operation] = ApiException(
              'connection_failed',
              status: status,
            );
            await c.refresh();
            expect(c.analysis, same(original));
            expect(c.report, isNull);
            expect(c.observations, isNull);
            expect(c.review, isNull);
            expect(c.needsRefresh, isTrue);
            expect(c.canEditReview, isFalse);
            // Retain the bound draft privately/in memory; never submit it stale.
            expect(
              c.fields['medicine']!.reviewedValue,
              '  UNSENT CORRECTION  ',
            );
            await c.submitReview('correct');
            expect(s.bodies, isEmpty);
            await c.refresh();
            expect(c.analysis!.version, 3);
            expect(c.report!.analysisVersion, 3);
            expect(c.review!.version, 3);
            expect(c.review!.revision, revision);
            expect(c.needsRefresh, isFalse);
            // A new binding requires new review; old corrections cannot migrate.
            expect(c.fields['medicine']!.status, 'unreviewed');
            c.dispose();
          },
        );
      }
    }
  }
  test('refresh installs the analysis and projections atomically', () async {
    final s = FakeAnalysisService();
    final c = await started(s);
    await c.beginReview();
    final original = c.analysis;
    final oldReport = c.report;
    s.currentStatus = {...s.currentStatus, 'version': 3};
    s.currentReport = {...s.currentReport, 'analysis_version': 3};
    s.currentContext = {...s.currentContext, 'version': 3};
    final wait = Completer<void>();
    s.reporting = wait;
    final calls = s.calls.where((name) => name == 'report').length;
    final refreshing = c.refresh();
    while (s.calls.where((name) => name == 'report').length == calls) {
      await Future<void>.delayed(Duration.zero);
    }
    expect(c.analysis, same(original));
    expect(c.report, same(oldReport));
    expect(c.canEditReview, isFalse);
    wait.complete();
    await refreshing;
    expect(c.analysis!.version, 3);
    expect(c.report!.analysisVersion, 3);
    expect(c.review!.version, 3);
    c.dispose();
  });
  test(
    'same-binding refresh recovery preserves unsent fields and dispositions',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s, prescription: true);
      await c.beginReview();
      c.correctField('$firstLineId.medicine', '  UNSENT LINE  ');
      c.disposition(firstLineId, 'included');
      c.disposition(secondLineId, 'excluded');
      await c.refresh();
      expect(
        c.fields['$firstLineId.medicine']!.reviewedValue,
        '  UNSENT LINE  ',
      );
      s.failures['reviewContext'] = const ApiException(
        'connection_failed',
        status: 503,
      );
      await c.refresh();
      expect(c.canEditReview, isFalse);
      expect(c.report, isNull);
      await c.refresh();
      expect(c.canEditReview, isTrue);
      expect(
        c.fields['$firstLineId.medicine']!.reviewedValue,
        '  UNSENT LINE  ',
      );
      expect(c.dispositions, {
        firstLineId: 'included',
        secondLineId: 'excluded',
      });
      c.dispose();
    },
  );
  test(
    'controlled workflow completes processing without confirmation, verification or medication writes',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s);
      expect(c.analysis!.job.state, 'completed');
      expect(c.review, isNull);
      expect(c.report!.reviewState, 'unreviewed');
      expect(c.report!.acceptedTranscription, isEmpty);
      expect(c.report!.fields.values.every((f) => f.value == null), isTrue);
      expect(s.calls, isNot(contains('submit')));
      c.dispose();
    },
  );
  test(
    'literal/null confirmation is complete and final review cannot reopen',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s);
      await c.beginReview();
      expect(c.fields.values.every((f) => f.status == 'unreviewed'), isTrue);
      await c.submitReview('confirm');
      expect(c.error, 'invalid_review');
      expect(s.bodies, isEmpty);
      confirmAll(c);
      await c.submitReview('confirm');
      expect(c.report!.acceptedTranscription['medicine'], ' TEST ITEM A ');
      expect(c.report!.acceptedTranscription['strength'], isNull);
      expect(c.report!.verificationStatus, 'unverified');
      expect(c.review!.closed, isTrue);
      expect(c.canEditReview, isFalse);
      expect(c.canNewAttempt, isFalse);
      await c.submitReview('correct');
      expect(s.bodies.length, 1);
      c.dispose();
    },
  );
  test(
    'unresolved review history restores corrections without accepting them',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s);
      await c.beginReview();
      c.correctField('medicine', '  TEST CORRECTION  ');
      await c.submitReview('unresolved');
      expect(c.report!.acceptedTranscription, isEmpty);
      expect(c.fields['medicine']!.reviewedValue, '  TEST CORRECTION  ');
      expect(c.review!.version, 3);
      confirmAll(c);
      c.correctField('medicine', null);
      await c.submitReview('correct');
      expect(c.report!.acceptedTranscription['medicine'], isNull);
      expect(
        c.report!.observations.medicine!.medicine.rawText,
        ' TEST ITEM A ',
      );
      c.dispose();
    },
  );
  test(
    'prescription lines require explicit dispositions and excluded lines are not accepted',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s, prescription: true);
      await c.beginReview();
      confirmAll(c);
      await c.submitReview('confirm');
      expect(c.error, 'invalid_review');
      c.disposition(firstLineId, 'included');
      c.disposition(secondLineId, 'excluded');
      await c.submitReview('confirm');
      expect(
        c.report!.acceptedTranscription.keys.every(
          (key) => key.startsWith(firstLineId),
        ),
        isTrue,
      );
      expect(c.report!.observations.lines.length, 2);
      expect(c.report!.observations.lines.first.fields.dose.rawText, isNull);
      c.dispose();
    },
  );
  test(
    'lost final receipt freezes editing and replays identical body/key after image deletion',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s);
      await c.beginReview();
      confirmAll(c);
      s.loseReviewReceipt = true;
      await c.submitReview('confirm');
      expect(c.uncertain, isTrue);
      c.correctField('medicine', 'changed');
      await c.retryPending();
      expect(s.receipts.length, 1);
      expect(s.requestKeys['submit']!.toSet().length, 1);
      expect(s.bodies[0], s.bodies[1]);
      expect(c.review!.closed, isTrue);
      expect(c.uncertain, isFalse);
      c.dispose();
    },
  );
  test(
    'failed and needs_input never display a completed report or accepted values',
    () async {
      for (final state in ['failed', 'needs_input']) {
        final s = FakeAnalysisService()..extractionState = state;
        final c = await started(s);
        expect(c.analysis!.job.state, state);
        expect(c.observations, isNull);
        expect(c.report, isNull);
        expect(c.canNewAttempt, isTrue);
        c.dispose();
      }
    },
  );
  test('disabled provider preserves queued job and never falls back', () async {
    final s = FakeAnalysisService()
      ..failures['extract'] = const ApiException(
        'provider_disabled',
        status: 503,
      );
    final c = await started(s);
    expect(c.analysis!.job.state, 'queued');
    expect(c.report, isNull);
    expect(s.calls.where((name) => name == 'extract').length, 1);
    c.dispose();
  });
  test(
    'new extraction keeps parent/deadline, creates an attempt and clears earlier draft',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s);
      await c.beginReview();
      c.correctField('medicine', 'user correction');
      final original = c.analysis!.expiresAt;
      await c.newAttempt();
      expect(c.analysis!.id, analysisId);
      expect(c.analysis!.expiresAt, original);
      expect(c.analysis!.job.attempt, 2);
      expect(c.report!.revision, 2);
      expect(c.fields, isEmpty);
      expect(s.requestKeys['extract']!.toSet().length, 2);
      c.dispose();
    },
  );
  test(
    'cancel interrupts a late extraction response without overwriting cancellation',
    () async {
      final wait = Completer<void>();
      final s = FakeAnalysisService()..extracting = wait;
      final c = SyntheticAnalysisController(s, () {});
      final starting = c.start(bundledFixtures[3], 'en-IN');
      while (!s.calls.contains('extract')) {
        await Future<void>.delayed(Duration.zero);
      }
      await c.cancel();
      expect(c.analysis!.availability, 'cancelled');
      wait.complete();
      await starting;
      expect(c.analysis!.availability, 'cancelled');
      expect(c.report, isNull);
      expect(c.canNewAttempt, isFalse);
      c.dispose();
    },
  );
  test(
    'expiry leaves saved transcription readable but blocks further review/retry',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s);
      await c.beginReview();
      s.currentStatus['availability'] = 'expired';
      s.currentReport['expired'] = true;
      s.currentReport['image_available'] = false;
      s.currentContext['image_available'] = false;
      await c.refresh();
      expect(c.report, isNotNull);
      expect(c.canEditReview, isFalse);
      final writes = s.bodies.length;
      await c.submitReview('confirm');
      await c.newAttempt();
      expect(s.bodies.length, writes);
      c.dispose();
    },
  );
  test(
    'stale mutation hides projections until current snapshot reload',
    () async {
      final s = FakeAnalysisService();
      final c = await started(s);
      s.failures['prepare'] = const ApiException('stale_version', status: 409);
      await c.beginReview();
      expect(c.needsRefresh, isTrue);
      expect(c.report, isNull);
      await c.refresh();
      expect(c.needsRefresh, isFalse);
      expect(c.report, isNotNull);
      c.dispose();
    },
  );
  test('erasure and expired authentication clear sensitive text', () async {
    for (final status in [401, 404]) {
      var expired = 0;
      final s = FakeAnalysisService();
      final c = SyntheticAnalysisController(s, () => expired++);
      await c.start(bundledFixtures[3], 'en-IN');
      s.failures['status'] = ApiException('not_found', status: status);
      await c.refresh();
      expect(c.analysis, isNull);
      expect(c.report, isNull);
      expect(c.fields, isEmpty);
      expect(expired, status == 401 ? 1 : 0);
      c.dispose();
    }
  });
  test('disposal discards late responses and clears session buffers', () async {
    final wait = Completer<void>();
    final s = FakeAnalysisService()..extracting = wait;
    final c = SyntheticAnalysisController(s, () {});
    final pending = c.start(bundledFixtures[3], 'en-IN');
    while (!s.calls.contains('extract')) {
      await Future<void>.delayed(Duration.zero);
    }
    c.dispose();
    wait.complete();
    await pending;
    expect(c.analysis, isNull);
    expect(c.observations, isNull);
    expect(s.cleared, isTrue);
  });
  test(
    'deadline crossing during an open review reports expiry and performs no write',
    () async {
      var now = DateTime.utc(2026);
      final s = FakeAnalysisService();
      final c = SyntheticAnalysisController(s, () {}, clock: () => now);
      await c.start(bundledFixtures[3], 'en-IN');
      await c.beginReview();
      confirmAll(c);
      now = DateTime.utc(2100);
      await c.submitReview('confirm');
      expect(c.error, 'analysis_expired');
      expect(s.bodies, isEmpty);
      expect(c.canEditReview, isFalse);
      expect(c.report, isNotNull);
      c.dispose();
    },
  );
}
