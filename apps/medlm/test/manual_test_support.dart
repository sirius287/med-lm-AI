import 'dart:async';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/medications/generated/manual_models.dart';
import 'package:medlm/medications/medication_service.dart';

const syntheticMedication = MedicationView(
  id: '00000000-0000-4000-8000-000000000001',
  displayName: 'Synthetic entry',
  strengthText: null,
  doseText: 'Literal instruction',
  routeText: null,
  instructions: null,
  version: 1,
  origin: 'manual',
  verificationStatus: 'unverified',
  deletedAt: null,
  schedule: null,
);
const syntheticDose = OccurrenceView(
  id: '00000000-0000-4000-8000-000000000002',
  medicationId: '00000000-0000-4000-8000-000000000001',
  plannedAt: '2026-10-05T02:30:00Z',
  originalLocalTime: '2026-10-05T08:00:00+05:30',
  doseSnapshot: {
    'display_name': 'Synthetic entry',
    'dose_text': 'Literal instruction',
  },
  status: 'pending',
  version: 1,
  latestEventId: null,
  actionable: true,
);

class SyntheticMedications extends MedicationService {
  SyntheticMedications()
    : super(
        ApiClient(
          'https://synthetic.invalid/api/v1',
          MockClient((_) async => http.Response('{}', 500)),
        ),
      );
  Object? failure;
  Completer<void>? pending;
  bool previewFails = false;
  int previewVersion = 1;
  int saves = 0, events = 0, activations = 0;
  final eventKeys = <String>[];
  Map<String, dynamic>? savedInput;
  List<HistoryView> historyItems = [];
  Future<void> wait() async {
    await pending?.future;
    if (failure != null) throw failure!;
  }

  @override
  Future<List<MedicationView>> list({bool includeDeleted = false}) async {
    await wait();
    return [syntheticMedication];
  }

  @override
  Future<List<OccurrenceView>> doses(DateTime date, String zone) async {
    await wait();
    return [syntheticDose];
  }

  @override
  Future<List<HistoryView>> history(
    DateTime start,
    DateTime end,
    String zone,
  ) async {
    await wait();
    return historyItems;
  }

  @override
  Future<MedicationView> get(String id) async {
    await wait();
    return syntheticMedication;
  }

  @override
  Future<MedicationView> save(
    Map<String, dynamic> fields,
    String key, {
    MedicationView? existing,
  }) async {
    await wait();
    saves++;
    savedInput = fields;
    return syntheticMedication;
  }

  @override
  Future<PreviewView> preview(
    String id,
    Map<String, dynamic> schedule,
    String key,
  ) async {
    await wait();
    if (previewFails) throw const ApiException('unavailable', status: 503);
    return PreviewView(
      proposalHash: 'synthetic-preview',
      expiresAt: '2030-01-01T00:00:00Z',
      medicationVersion: previewVersion,
      occurrences: [
        {
          'planned_at': '2030-01-01T02:30:00Z',
          'original_local_time': '2030-01-01T08:00:00+05:30',
        },
      ],
      warnings: [],
    );
  }

  @override
  Future<MedicationView> activate(
    String id,
    Map<String, dynamic> schedule,
    PreviewView preview,
    String key,
  ) async {
    await wait();
    activations++;
    return syntheticMedication;
  }

  @override
  Future<void> event(
    OccurrenceView dose,
    String type,
    String key, {
    String? correction,
    required DateTime at,
  }) async {
    eventKeys.add(key);
    await wait();
    events++;
  }
}
