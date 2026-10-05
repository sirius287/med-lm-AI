import 'package:flutter/foundation.dart';
import '../core/api_client.dart';
import 'generated/manual_models.dart';
import 'medication_service.dart';

/// Memory only. Disposing the owner scope rejects late responses and clears data.
class MedicationController extends ChangeNotifier {
  MedicationController(this.service, this.onExpired);
  final MedicationService service;
  final VoidCallback onExpired;
  List<MedicationView> medications = [];
  List<OccurrenceView> doses = [];
  List<HistoryView> history = [];
  bool busy = false;
  bool initialized = false;
  bool historyInitialized = false;
  bool includeRemoved = false;
  String? error;
  bool _disposed = false;
  int _generation = 0;
  String zone = 'Asia/Kolkata';
  // Today's India-first display day is independent of device timezone/travel.
  DateTime get today =>
      DateTime.now().toUtc().add(const Duration(hours: 5, minutes: 30));

  Future<void> run(Future<void> Function(int generation) action) async {
    if (busy || _disposed) return;
    final generation = ++_generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await action(generation);
    } on ApiException catch (e) {
      if (current(generation)) {
        error = e.code;
        if (e.status == 401) onExpired();
      }
    } catch (_) {
      if (current(generation)) error = 'unavailable';
    } finally {
      if (current(generation)) {
        busy = false;
        notifyListeners();
      }
    }
  }

  bool current(int generation) => !_disposed && generation == _generation;
  Future<void> refresh() => run((generation) async {
    initialized = true;
    final m = await service.list(includeDeleted: includeRemoved);
    final d = await service.doses(today, zone);
    if (current(generation)) {
      medications = m;
      doses = d;
    }
  });
  Future<void> loadHistory(DateTime start, DateTime end) =>
      run((generation) async {
        historyInitialized = true;
        final h = await service.history(start, end, zone);
        if (current(generation)) history = h;
      });
  Future<void> correctHistory(
    HistoryView event,
    String status,
    DateTime start,
    DateTime end,
  ) => run((generation) async {
    final dose = await service.historyOccurrence(event);
    if (dose.latestEventId != event.id || !dose.actionable) {
      throw const ApiException('dose_conflict', status: 409);
    }
    final operation = '${dose.id}:${dose.version}:corrected:$status';
    final attempt = _attempts.putIfAbsent(
      operation,
      () => (requestId(), DateTime.now()),
    );
    await service.event(
      dose,
      'corrected',
      attempt.$1,
      correction: status,
      at: attempt.$2,
    );
    final h = await service.history(start, end, zone);
    if (current(generation)) {
      history = h;
      _attempts.remove(operation);
    }
  });
  final _attempts = <String, (String, DateTime)>{};
  Future<void> record(OccurrenceView dose, String type, {String? correction}) =>
      run((generation) async {
        final operation = '${dose.id}:${dose.version}:$type:$correction';
        final attempt = _attempts.putIfAbsent(
          operation,
          () => (requestId(), DateTime.now()),
        );
        await service.event(
          dose,
          type,
          attempt.$1,
          correction: correction,
          at: attempt.$2,
        );
        final d = await service.doses(today, zone);
        if (current(generation)) {
          doses = d;
          _attempts.remove(operation);
        }
      });
  @override
  void dispose() {
    _disposed = true;
    _generation++;
    medications = [];
    doses = [];
    history = [];
    _attempts.clear();
    super.dispose();
  }
}
