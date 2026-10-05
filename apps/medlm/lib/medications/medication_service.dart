import 'dart:math';
import '../core/api_client.dart';
import 'generated/manual_models.dart';

String requestId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

String isoDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

class MedicationService {
  MedicationService(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> call(
    String method,
    String path, {
    Map<String, dynamic>? body,
    String? key,
    int? version,
  }) => api.request(
    method,
    path,
    authenticated: true,
    body: body,
    headers: {
      'Idempotency-Key': ?key,
      if (version != null) 'If-Match': '"$version"',
    },
  );
  Future<List<T>> pages<T>(
    String path,
    T Function(Map<String, dynamic>) decode,
  ) async {
    final items = <T>[];
    String? cursor;
    do {
      final result = await call(
        'GET',
        '$path${path.contains('?') ? '&' : '?'}limit=100${cursor == null ? '' : '&cursor=${Uri.encodeQueryComponent(cursor)}'}',
      );
      items.addAll(
        (result['items'] as List).map((e) => decode(e as Map<String, dynamic>)),
      );
      cursor = result['next_cursor'] as String?;
      if (items.length > 10000) throw const ApiException('range_too_large');
    } while (cursor != null);
    return items;
  }

  Future<List<MedicationView>> list({bool includeDeleted = false}) => pages(
    '/medications?include_deleted=$includeDeleted',
    MedicationView.fromJson,
  );
  Future<MedicationView> get(String id) async =>
      MedicationView.fromJson(await call('GET', '/medications/$id'));
  Future<MedicationView> save(
    Map<String, dynamic> fields,
    String key, {
    MedicationView? existing,
  }) async => MedicationView.fromJson(
    await call(
      existing == null ? 'POST' : 'PATCH',
      existing == null ? '/medications' : '/medications/${existing.id}',
      body: fields,
      key: existing == null ? key : null,
      version: existing?.version,
    ),
  );
  Future<PreviewView> preview(
    String id,
    Map<String, dynamic> schedule,
    String key,
  ) async => PreviewView.fromJson(
    await call(
      'POST',
      '/medications/$id/schedules/preview',
      body: schedule,
      key: key,
    ),
  );
  Future<MedicationView> activate(
    String id,
    Map<String, dynamic> schedule,
    PreviewView preview,
    String key,
  ) async => MedicationView.fromJson(
    await call(
      'POST',
      '/medications/$id/schedules',
      key: key,
      body: {
        'schedule': schedule,
        'proposal_hash': preview.proposalHash,
        'expires_at': preview.expiresAt,
        'medication_version': preview.medicationVersion,
      },
    ),
  );
  Future<void> remove(MedicationView medication, {required bool erase}) async {
    await call(
      'DELETE',
      '/medications/${medication.id}?erase_history=$erase',
      version: medication.version,
    );
  }

  Future<List<OccurrenceView>> doses(DateTime date, String zone) async {
    // Include adjacent local dates so mixed schedule timezones cover the selected day.
    await call(
      'POST',
      '/occurrences/materialize',
      key: requestId(),
      body: {
        'from_date': isoDate(date.subtract(const Duration(days: 1))),
        'to_date': isoDate(date.add(const Duration(days: 1))),
      },
    );
    return pages(
      '/occurrences?from_date=${isoDate(date)}&to_date=${isoDate(date)}&time_zone=${Uri.encodeQueryComponent(zone)}',
      OccurrenceView.fromJson,
    );
  }

  Future<void> event(
    OccurrenceView dose,
    String type,
    String key, {
    String? correction,
    required DateTime at,
  }) async {
    await call(
      'POST',
      '/occurrences/${dose.id}/events',
      key: key,
      body: {
        'event_id': key,
        'type': type,
        'expected_version': dose.version,
        'client_at': at.toUtc().toIso8601String(),
        'corrected_status': ?correction,
        if (correction != null) 'supersedes_event_id': dose.latestEventId,
      },
    );
  }

  Future<List<HistoryView>> history(
    DateTime start,
    DateTime end,
    String zone,
  ) => pages(
    '/history?from_date=${isoDate(start)}&to_date=${isoDate(end)}&time_zone=${Uri.encodeQueryComponent(zone)}',
    HistoryView.fromJson,
  );

  Future<OccurrenceView> historyOccurrence(HistoryView event) async {
    final instant = DateTime.tryParse(event.originalLocalTime ?? '');
    if (instant == null) throw const ApiException('dose_conflict', status: 409);
    final date = instant.toUtc().add(const Duration(hours: 5, minutes: 30));
    final items = await pages(
      '/occurrences?from_date=${isoDate(date)}&to_date=${isoDate(date)}&time_zone=Asia%2FKolkata',
      OccurrenceView.fromJson,
    );
    for (final item in items) {
      if (item.id == event.occurrenceId) return item;
    }
    throw const ApiException('dose_conflict', status: 409);
  }
}
