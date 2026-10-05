import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/app/app.dart';
import 'package:medlm/app/providers.dart';
import 'package:medlm/auth/auth_controller.dart';
import 'package:medlm/l10n/app_localizations.dart';
import 'package:medlm/medications/medication_form_screen.dart';
import 'package:medlm/medications/medication_providers.dart';
import 'package:medlm/medications/dashboard_screen.dart';
import 'package:medlm/medications/generated/manual_models.dart';
import 'auth_controller_test.dart' show SyntheticAuth;
import 'manual_test_support.dart';

Future<void> showManual(
  WidgetTester tester,
  SyntheticMedications service, {
  bool signedIn = true,
}) async {
  final auth = SyntheticAuth()..user = signedIn ? 'synthetic-user' : null;
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        startupProvider.overrideWith((ref) async {}),
        accountProvider.overrideWith(
          (ref) => AuthController(auth, initialize: () async {}),
        ),
        medicationServiceProvider.overrideWithValue(service),
      ],
      child: const MedlmApp(),
    ),
  );
  await tester.pumpAndSettle();
}

class HistoryDateService extends SyntheticMedications {
  final ranges = <(DateTime, DateTime)>[];
  @override
  Future<List<HistoryView>> history(
    DateTime start,
    DateTime end,
    String zone,
  ) async {
    ranges.add((start, end));
    return historyItems;
  }

  @override
  Future<OccurrenceView> historyOccurrence(HistoryView event) async =>
      OccurrenceView(
        id: event.occurrenceId,
        medicationId: syntheticDose.medicationId,
        plannedAt: syntheticDose.plannedAt,
        originalLocalTime: event.originalLocalTime,
        doseSnapshot: event.doseSnapshot,
        status: 'taken',
        version: 2,
        latestEventId: event.id,
        actionable: true,
      );
}

void main() {
  testWidgets(
    'history correction uses applied dates despite invalid draft dates',
    (tester) async {
      final service = HistoryDateService()
        ..historyItems = [
          const HistoryView(
            id: 'synthetic-event',
            occurrenceId: 'synthetic-dose',
            kind: 'taken',
            clientAt: '2026-10-05T03:00:00Z',
            recordedAt: '2026-10-05T03:00:00Z',
            supersedesEventId: null,
            payload: {},
            doseSnapshot: {
              'display_name': 'Synthetic entry',
              'dose_text': 'Literal instruction',
            },
            originalLocalTime: '2026-10-05T08:00:00+05:30',
          ),
        ];
      await showManual(tester, service);
      await tester.tap(find.text('Dose history'));
      await tester.pumpAndSettle();
      final inputs = find.byType(TextFormField);
      await tester.enterText(inputs.at(0), '2026-10-01');
      await tester.enterText(inputs.at(1), '2026-10-05');
      await tester.ensureVisible(find.text('Apply date range (up to 90 days)'));
      await tester.tap(find.text('Apply date range (up to 90 days)'));
      await tester.pumpAndSettle();
      final applied = service.ranges.last;
      expect(applied, (DateTime(2026, 10, 1), DateTime(2026, 10, 5)));
      await tester.ensureVisible(inputs.at(0));
      await tester.enterText(inputs.at(0), 'invalid');
      await tester.enterText(inputs.at(1), '');
      tester.testTextInput.hide();
      await tester.scrollUntilVisible(
        find.text('Correct recorded action'),
        150,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Correct recorded action'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Skipped'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(service.events, 1);
      expect(service.ranges.last, applied);
    },
  );
  testWidgets(
    'history shows the replacement status of an explicit correction',
    (tester) async {
      final service = SyntheticMedications()
        ..historyItems = [
          const HistoryView(
            id: 'synthetic-event',
            occurrenceId: 'synthetic-dose',
            kind: 'corrected',
            clientAt: '2026-10-05T03:00:00Z',
            recordedAt: '2026-10-05T03:00:00Z',
            supersedesEventId: 'previous-event',
            payload: {'corrected_status': 'skipped'},
            doseSnapshot: {
              'display_name': 'Synthetic entry',
              'dose_text': 'Literal instruction',
            },
            originalLocalTime: '2026-10-05T08:00:00+05:30',
          ),
        ];
      await showManual(tester, service);
      await tester.tap(find.text('Dose history'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Correction: Skipped'),
        150,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Correction: Skipped'), findsOneWidget);
    },
  );
  testWidgets('successful email login navigates to the manual dashboard', (
    tester,
  ) async {
    await showManual(tester, SyntheticMedications(), signedIn: false);
    await tester.tap(find.byKey(const Key('account')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('email')), 'test@example.org');
    await tester.enterText(
      find.byKey(const Key('password')),
      'synthetic-password',
    );
    await tester.ensureVisible(find.byKey(const Key('submit-auth')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('submit-auth')));
    await tester.pumpAndSettle();
    expect(find.byType(DashboardScreen), findsOneWidget);
  });
  testWidgets('account changes discard an unsaved medication form', (
    tester,
  ) async {
    await showManual(tester, SyntheticMedications());
    await tester.tap(find.text('Add medication'));
    await tester.pumpAndSettle();
    final s = AppLocalizations.of(
      tester.element(find.byType(MedicationFormScreen)),
    )!;
    final field = find.widgetWithText(TextFormField, s.medicineName);
    await tester.ensureVisible(field);
    await tester.enterText(field, 'Synthetic private draft');
    final container = ProviderScope.containerOf(
      tester.element(find.byType(MedicationFormScreen)),
    );
    final account = container.read(accountProvider);
    (account.service as SyntheticAuth).user = 'second-synthetic-user';
    await account.restore();
    await tester.pumpAndSettle();
    expect(find.text('Synthetic private draft'), findsNothing);
  });
  testWidgets(
    'restored login opens dashboard and logout removes personal routes',
    (tester) async {
      await showManual(tester, SyntheticMedications());
      expect(find.byType(DashboardScreen), findsOneWidget);
      final initialContainer = ProviderScope.containerOf(
        tester.element(find.byType(DashboardScreen)),
      );
      expect(initialContainer.read(medicationControllerProvider).error, isNull);
      expect(
        initialContainer.read(medicationControllerProvider).doses.length,
        1,
      );
      await tester.scrollUntilVisible(find.text('Synthetic entry'), 150);
      expect(find.text('Synthetic entry'), findsOneWidget);
      final container = ProviderScope.containerOf(
        tester.element(find.byType(DashboardScreen)),
      );
      await container.read(accountProvider).logout();
      await tester.pumpAndSettle();
      expect(find.text('Synthetic entry'), findsNothing);
      container.read(routerProvider).go('/medications/new');
      await tester.pumpAndSettle();
      expect(find.byType(MedicationFormScreen), findsNothing);
    },
  );
  for (final stale in [false, true]) {
    testWidgets(
      'partial save recovery rejects stale preview=$stale without duplicate medication',
      (tester) async {
        final service = SyntheticMedications()..previewFails = true;
        await showManual(tester, service);
        await tester.tap(find.text('Add medication'));
        await tester.pumpAndSettle();
        final s = AppLocalizations.of(
          tester.element(find.byType(MedicationFormScreen)),
        )!;
        Future<void> fill(String label, String value) async {
          final finder = find.widgetWithText(TextFormField, label);
          await tester.ensureVisible(finder);
          await tester.enterText(finder, value);
        }

        await fill(s.medicineName, 'Synthetic entry');
        await fill(s.doseText, 'Literal instruction');
        await fill(s.startDate, '2030-01-01');
        await fill(s.endDate, '2030-01-03');
        await fill(s.clockTimes, '08:00');
        tester.testTextInput.hide();
        await tester.pumpAndSettle();
        await tester.ensureVisible(find.text(s.saveAndPreview));
        await tester.pumpAndSettle();
        await tester.tap(find.text(s.saveAndPreview));
        await tester.pumpAndSettle();
        expect(service.saves, 1);
        expect(service.activations, 0);
        await tester.scrollUntilVisible(
          find.text(s.savedNoSchedule),
          -200,
          scrollable: find.byType(Scrollable).first,
        );
        expect(find.text(s.savedNoSchedule), findsOneWidget);
        service.previewFails = false;
        service.previewVersion = stale ? 2 : 1;
        await tester.ensureVisible(find.text(s.saveAndPreview));
        await tester.pumpAndSettle();
        await tester.tap(find.text(s.saveAndPreview));
        await tester.pumpAndSettle();
        expect(service.saves, 1);
        if (stale) {
          expect(find.text(s.activateSchedule), findsNothing);
          await tester.scrollUntilVisible(
            find.text(s.manualConflict),
            -200,
            scrollable: find.byType(Scrollable).first,
          );
          expect(find.text(s.manualConflict), findsOneWidget);
          expect(service.activations, 0);
          return;
        }
        await tester.ensureVisible(find.text(s.activateSchedule));
        expect(find.text(s.activateSchedule), findsOneWidget);
        await tester.tap(find.text(s.activateSchedule));
        await tester.pumpAndSettle();
        expect(service.activations, 1);
      },
    );
  }
}
