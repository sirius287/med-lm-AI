import 'package:flutter/foundation.dart';
import '../core/api_client.dart';
import '../medications/medication_service.dart' show requestId;
import 'analysis_validation.dart';
import 'generated/analysis_models.dart';
import 'generated/synthetic_fixture_catalog.dart';
import 'synthetic_analysis_service.dart';

enum SyntheticPage { fixtures, observations, review, report }

class _Start {
  _Start(this.fixture, this.locale);
  final BundledFixture fixture;
  final String locale;
  final uploadKey = requestId(),
      createKey = requestId(),
      leaseKey = requestId(),
      extractKey = requestId();
  String? upload;
  AnalysisView? created;
  LeaseView? leased;
}

/// Memory-only owner scope. The server remains the authority for every mutation.
class SyntheticAnalysisController extends ChangeNotifier {
  SyntheticAnalysisController(
    this.service,
    this.onExpired, {
    DateTime Function()? clock,
  }) : clock = clock ?? DateTime.now;
  final SyntheticAnalysisService service;
  final VoidCallback onExpired;
  final DateTime Function() clock;
  SyntheticPage page = SyntheticPage.fixtures;
  AnalysisView? analysis;
  ExtractionResult? observations;
  ReviewContext? review;
  AnalysisReport? report;
  ReviewReceipt? receipt;
  BundledFixture? fixture;
  String? error;
  bool busy = false, uncertain = false, needsRefresh = false;
  bool _disposed = false;
  bool _authorized = true;
  int _generation = 0;
  Future<void> Function(int)? _pending;
  ReviewContext? _draftContext;
  final _fields = <String, FieldReview>{};
  final _dispositions = <String, String>{};
  Map<String, FieldReview> get fields => Map.unmodifiable(_fields);
  Map<String, String> get dispositions => Map.unmodifiable(_dispositions);
  bool get isExpired =>
      analysis != null &&
      !clock().toUtc().isBefore(DateTime.parse(analysis!.expiresAt));
  bool _expiryFeedback() {
    if (!isExpired) return false;
    error = 'analysis_expired';
    notifyListeners();
    return true;
  }

  bool get canMutate =>
      _authorized &&
      !_disposed &&
      analysis != null &&
      analysis!.availability == 'available' &&
      clock().toUtc().isBefore(DateTime.parse(analysis!.expiresAt)) &&
      review?.closed != true;
  bool get canEditReview =>
      canMutate &&
      review != null &&
      report != null &&
      review!.analysisId == analysis!.id &&
      review!.version == analysis!.version &&
      review!.revision == analysis!.resultRevision &&
      report!.analysisVersion == analysis!.version &&
      !busy &&
      !uncertain &&
      !needsRefresh;
  bool get canNewAttempt =>
      canMutate &&
      !busy &&
      !uncertain &&
      !needsRefresh &&
      [
        'completed',
        'failed',
        'needs_input',
        'queued',
        'extracting',
      ].contains(analysis!.job.state);
  bool current(int generation) =>
      !_disposed && _authorized && generation == _generation;

  /// Temporarily lock a same-owner workflow without losing draft/replay identity.
  /// Failed authentication and owner boundaries erase it instead. No late request
  /// from before revalidation may install state or continue its mutation chain.
  void updateAuthorization({
    required bool authenticated,
    required bool revalidating,
  }) {
    if (_disposed) return;
    if (authenticated) {
      if (!_authorized) {
        _authorized = true;
        notifyListeners();
      }
      return;
    }
    if (_authorized) {
      _authorized = false;
      _generation++;
      if (busy) {
        if (_pending != null) uncertain = true;
        needsRefresh = analysis != null;
        _projectionClear(preserveDraft: true);
      }
      busy = false;
      service.clearSession();
    }
    if (!revalidating) {
      _generation++;
      _clear();
      fixture = null;
      page = SyntheticPage.fixtures;
      error = null;
    }
    notifyListeners();
  }

  Future<void> _run(
    Future<void> Function(int) action, {
    bool mutation = false,
    bool interrupt = false,
  }) async {
    if (_disposed || !_authorized || (busy && !interrupt)) return;
    final generation = ++_generation;
    busy = true;
    error = null;
    if (mutation) _pending = action;
    notifyListeners();
    try {
      await action(generation);
      if (current(generation) && mutation) {
        _pending = null;
        uncertain = false;
      }
    } on ApiException catch (e) {
      if (!current(generation)) return;
      error = e.code;
      if (e.status == 401) {
        _clear();
        service.clearSession();
        onExpired();
      } else if (e.status == 404) {
        _clear();
      } else if ([409, 410, 412].contains(e.status)) {
        needsRefresh = true;
        _projectionClear(preserveDraft: true);
        _pending = null;
        uncertain = false;
      } else if (mutation && (e.status == null || e.status! >= 500)) {
        uncertain = true;
      } else if (mutation) {
        _pending = null;
        uncertain = false;
      }
    } on FormatException {
      if (current(generation)) {
        error = 'invalid_response';
        needsRefresh = true;
        _projectionClear(preserveDraft: true);
      }
    } finally {
      if (current(generation)) {
        busy = false;
        notifyListeners();
      }
    }
  }

  Future<void> start(BundledFixture selected, String locale) async {
    if (_disposed || !_authorized || busy || uncertain || analysis != null) {
      return;
    }
    fixture = selected;
    final attempt = _Start(selected, locale);
    page = SyntheticPage.observations;
    await _run((generation) async {
      attempt.upload ??= await service.upload(
        attempt.fixture,
        attempt.uploadKey,
      );
      if (!current(generation)) return;
      attempt.created ??= await service.create(
        attempt.upload!,
        attempt.fixture,
        attempt.locale,
        attempt.createKey,
      );
      if (!current(generation)) return;
      analysis = attempt.created;
      notifyListeners();
      attempt.leased ??= await service.lease(
        attempt.created!,
        attempt.leaseKey,
      );
      if (!current(generation)) return;
      final result = await service.extract(attempt.leased!, attempt.extractKey);
      if (!current(generation)) return;
      _extracted(result, attempt.fixture);
      await _read(generation);
    }, mutation: true);
  }

  void _extracted(ExtractResponse result, BundledFixture? selected) {
    if (result.revision != null &&
        selected != null &&
        (result.revision!.provenance.fixtureId != selected.id ||
            result.revision!.provenance.sourceSha256 != selected.originalHash ||
            result.metadata?.sanitizedSha256 != selected.sanitizedHash ||
            result.revision!.extraction.documentKind != selected.kind)) {
      invalidAnalysis();
    }
    analysis = result.status;
    observations = result.revision?.extraction;
    error = result.error?.code;
  }

  Future<void> _read(int generation, {String? identity}) async {
    final id = identity ?? analysis!.id;
    try {
      final status = await service.status(id);
      if (!current(generation)) return;
      if (status.job.state != 'completed' || status.resultRevision == null) {
        _projectionClear();
        analysis = status;
        needsRefresh = false;
        return;
      }
      final saved = await service.report(id, status.resultRevision!);
      if (!current(generation)) return;
      if (saved.analysisVersion != status.version) {
        throw const ApiException('stale_snapshot', status: 409);
      }
      ReviewContext? context;
      try {
        context = await service.reviewContext(id);
      } on ApiException catch (e) {
        if (e.code != 'review_not_prepared' || e.status != 409) rethrow;
      }
      if (!current(generation)) return;
      if (context != null &&
          (context.version != saved.analysisVersion ||
              context.revision != saved.revision ||
              !sameAnalysisJson(
                context.extraction.toJson(),
                saved.observations.toJson(),
              ))) {
        throw const ApiException('stale_snapshot', status: 409);
      }
      // Install one validated snapshot with no notification/await between parts.
      analysis = status;
      report = saved;
      observations = saved.observations;
      review = context;
      needsRefresh = false;
      if (context != null) _draft(context, saved);
    } on ApiException {
      if (current(generation)) _incompleteSnapshot();
      rethrow;
    } on FormatException {
      if (current(generation)) _incompleteSnapshot();
      rethrow;
    }
  }

  void _incompleteSnapshot() {
    needsRefresh = true;
    _projectionClear(preserveDraft: true);
  }

  Future<void> refresh() async {
    if (analysis == null) return;
    await _run(_read);
  }

  Future<void> open(String id) => _run((generation) async {
    page = SyntheticPage.observations;
    await _read(generation, identity: id);
  });

  Future<void> retryPending() async {
    final action = _pending;
    if (action != null && uncertain) await _run(action, mutation: true);
  }

  Future<void> newAttempt() async {
    if (_expiryFeedback()) return;
    if (!canNewAttempt) return;
    final target = analysis!;
    final key = requestId(), leaseKey = requestId(), extractKey = requestId();
    AnalysisView? created;
    LeaseView? leased;
    _projectionClear();
    await _run((generation) async {
      created ??= await service.newAttempt(target, key);
      if (!current(generation)) return;
      analysis = created;
      leased ??= await service.lease(created!, leaseKey);
      if (!current(generation)) return;
      final result = await service.extract(leased!, extractKey);
      if (!current(generation)) return;
      _extracted(result, fixture);
      await _read(generation);
    }, mutation: true);
  }

  Future<void> cancel() async {
    if (analysis == null || !canMutate) return;
    final id = analysis!.id, key = requestId();
    AnalysisView? target;
    service.clearSession();
    await _run(
      (generation) async {
        target ??= await service.status(id);
        if (!current(generation)) return;
        final result = await service.cancel(target!, key);
        if (!current(generation)) return;
        analysis = result;
        await _read(generation);
      },
      mutation: true,
      interrupt: true,
    );
  }

  Future<void> beginReview() async {
    if (!_authorized || _disposed) return;
    if (review != null) {
      page = SyntheticPage.review;
      notifyListeners();
      return;
    }
    if (_expiryFeedback()) return;
    if (!canMutate || busy || uncertain || analysis!.job.state != 'completed') {
      return;
    }
    final target = analysis!, key = requestId();
    await _run((generation) async {
      final context = await service.prepare(target, key);
      if (!current(generation)) return;
      final saved = await service.report(target.id, context.revision);
      if (!current(generation)) return;
      if (saved.analysisVersion != context.version ||
          !sameAnalysisJson(
            saved.observations.toJson(),
            context.extraction.toJson(),
          )) {
        throw const ApiException('stale_snapshot', status: 409);
      }
      review = context;
      report = saved;
      observations = context.extraction;
      _draft(context, saved);
      page = SyntheticPage.review;
    }, mutation: true);
  }

  void _draft(ReviewContext context, AnalysisReport saved) {
    final priorContext = _draftContext;
    if (!context.closed &&
        priorContext != null &&
        priorContext.analysisId == context.analysisId &&
        priorContext.revision == context.revision &&
        priorContext.version == context.version &&
        priorContext.candidateSetId == context.candidateSetId &&
        sameAnalysisJson(
          priorContext.extraction.toJson(),
          context.extraction.toJson(),
        )) {
      // Unsent input is reusable only against its exact original review binding.
      _draftContext = context;
      return;
    }
    _draftContext = context;
    _fields.clear();
    _dispositions.clear();
    final prior = saved.reviewHistory.lastOrNull?.review;
    if (prior != null && prior.candidateSetId == context.candidateSetId) {
      _fields.addAll(prior.fields);
      _dispositions.addAll(prior.lineDispositions);
    } else {
      for (final key in context.requiredFieldKeys) {
        _fields[key] = FieldReview.fromJson({
          'status': 'unreviewed',
          'reviewed_value': null,
        });
      }
    }
  }

  void confirmField(String key) {
    if (!canEditReview || !_fields.containsKey(key)) return;
    _fields[key] = FieldReview.fromJson({
      'status': 'confirmed',
      'reviewed_value': observedFields(review!.extraction)[key]!.rawText,
    });
    notifyListeners();
  }

  void correctField(String key, String? value) {
    if (!canEditReview || !_fields.containsKey(key)) return;
    try {
      _fields[key] = FieldReview.fromJson({
        'status': 'corrected',
        'reviewed_value': value,
      });
      error = null;
    } on FormatException {
      _fields[key] = FieldReview.fromJson({
        'status': 'unresolved',
        'reviewed_value': null,
      });
      error = 'invalid_review';
    }
    notifyListeners();
  }

  void unresolvedField(String key) {
    if (!canEditReview || !_fields.containsKey(key)) return;
    _fields[key] = FieldReview.fromJson({
      'status': 'unresolved',
      'reviewed_value': null,
    });
    notifyListeners();
  }

  void disposition(String id, String value) {
    if (!canEditReview ||
        !review!.extraction.lines.any((line) => line.lineId == id) ||
        !['included', 'excluded', 'unresolved'].contains(value)) {
      return;
    }
    _dispositions[id] = value;
    notifyListeners();
  }

  Future<void> submitReview(String decision) async {
    if (_expiryFeedback()) return;
    if (!canEditReview) return;
    HumanReview body;
    try {
      body = HumanReview.fromJson({
        'version': review!.version,
        'revision': review!.revision,
        'candidate_set_id': review!.candidateSetId,
        'candidate_id': null,
        'decision': decision,
        'fields': {
          for (final entry in _fields.entries) entry.key: entry.value.toJson(),
        },
        'line_dispositions': Map<String, String>.from(_dispositions),
      });
      validateHumanReview(body, review!.extraction);
    } on FormatException {
      error = 'invalid_review';
      notifyListeners();
      return;
    }
    final id = analysis!.id, key = requestId();
    await _run((generation) async {
      final result = await service.submit(id, body, key);
      if (!current(generation)) return;
      receipt = result;
      await _read(generation);
      if (!current(generation)) return;
      page = result.isFinal ? SyntheticPage.report : SyntheticPage.review;
    }, mutation: true);
  }

  void showReport() {
    if (report != null) {
      page = SyntheticPage.report;
      notifyListeners();
    }
  }

  void showObservations() {
    page = SyntheticPage.observations;
    notifyListeners();
  }

  void reset() {
    if (busy || uncertain || (analysis != null && canMutate)) return;
    _clear();
    fixture = null;
    page = SyntheticPage.fixtures;
    error = null;
    notifyListeners();
  }

  void _projectionClear({bool preserveDraft = false}) {
    observations = null;
    review = null;
    report = null;
    receipt = null;
    if (!preserveDraft) {
      _draftContext = null;
      _fields.clear();
      _dispositions.clear();
    }
  }

  void _clear() {
    analysis = null;
    _projectionClear();
    _pending = null;
    uncertain = false;
    needsRefresh = false;
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    service.clearSession();
    _clear();
    fixture = null;
    super.dispose();
  }
}
