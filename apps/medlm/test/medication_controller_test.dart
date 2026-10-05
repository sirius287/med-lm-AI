import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/medications/medication_controller.dart';
import 'manual_test_support.dart';

void main() {
  test('dispose clears medical state and rejects late results', () async {
    final service = SyntheticMedications();
    final controller = MedicationController(service, () {});
    await controller.refresh();
    expect(controller.medications, isNotEmpty);
    service.pending = Completer<void>();
    final loading = controller.refresh();
    controller.dispose();
    service.pending!.complete();
    await loading;
    expect(controller.medications, isEmpty);
    expect(controller.doses, isEmpty);
  });
  test(
    '401 expires session and safe error state never contains raw details',
    () async {
      var expired = false;
      final service = SyntheticMedications()
        ..failure = const ApiException('invalid_session', status: 401);
      final controller = MedicationController(service, () => expired = true);
      await controller.refresh();
      expect(expired, isTrue);
      expect(controller.error, 'invalid_session');
      expect(controller.busy, isFalse);
      controller.dispose();
    },
  );
  test(
    'retry retains event identity and duplicate taps do not create requests',
    () async {
      final service = SyntheticMedications()..pending = Completer<void>();
      final controller = MedicationController(service, () {});
      final first = controller.record(syntheticDose, 'taken');
      await controller.record(syntheticDose, 'taken');
      service.failure = const ApiException('connection_failed');
      service.pending!.complete();
      await first;
      expect(service.eventKeys.length, 1);
      service.failure = null;
      service.pending = null;
      await controller.record(syntheticDose, 'taken');
      expect(service.eventKeys[0], service.eventKeys[1]);
      expect(service.events, 1);
      controller.dispose();
    },
  );
}
