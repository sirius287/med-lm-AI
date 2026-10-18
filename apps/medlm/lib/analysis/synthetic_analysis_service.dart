import '../core/api_client.dart';
import '../uploads/synthetic_upload_service.dart';
import 'analysis_validation.dart';
import 'generated/analysis_models.dart';
import 'generated/synthetic_fixture_catalog.dart';

class SyntheticAnalysisService {
  SyntheticAnalysisService(this.api) : uploads = SyntheticUploadService(api);
  final ApiClient api;
  final SyntheticUploadService uploads;

  void clearSession() => uploads.clearSession();
  String path(String id) {
    if (!RegExp(
      r'^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$',
    ).hasMatch(id)) {
      throw const ApiException('invalid_analysis_id');
    }
    return '/analyses/$id';
  }

  Future<T> call<T>(
    String method,
    String path,
    T Function(Map<String, dynamic>) decode, {
    Map<String, dynamic>? body,
    String? key,
  }) async {
    final json = await api.request(
      method,
      path,
      authenticated: true,
      body: body,
      headers: {'Idempotency-Key': ?key},
    );
    try {
      return decode(json);
    } on FormatException {
      throw const ApiException('invalid_response');
    } on TypeError {
      throw const ApiException('invalid_response');
    }
  }

  Future<String> upload(BundledFixture fixture, String key) async {
    if (!bundledFixtures.contains(fixture)) {
      throw const ApiException('invalid_fixture');
    }
    final bytes = fixture.bytes();
    try {
      final result = await uploads.upload(
        fixture: bytes,
        checksum: fixture.originalHash,
        requestKey: key,
        documentKind: fixture.kind,
        retainForReview: true,
        resumeCompletion: true,
      );
      if (result['status'] != 'accepted' || result['upload_id'] is! String) {
        throw const ApiException('upload_unavailable');
      }
      final id = result['upload_id'] as String;
      path(id); // UUID only; never follow server-supplied URLs.
      return id;
    } finally {
      bytes.fillRange(0, bytes.length, 0);
    }
  }

  Future<AnalysisView> create(
    String uploadId,
    BundledFixture fixture,
    String locale,
    String key,
  ) => call(
    'POST',
    '/analyses',
    AnalysisView.fromJson,
    key: key,
    body: CreateAnalysis.fromJson({
      'upload_id': uploadId,
      'document_kind': fixture.kind,
      'content_type': fixture.mime,
      'retain_for_review': true,
      'locale': locale,
    }).toJson(),
  );

  AnalysisView ownedStatus(Map<String, dynamic> json, String id) {
    final result = AnalysisView.fromJson(json);
    if (result.id != id) invalidAnalysis();
    return result;
  }

  Future<AnalysisView> status(String id) =>
      call('GET', path(id), (json) => ownedStatus(json, id));
  Future<AnalysisView> newAttempt(AnalysisView a, String key) => call(
    'POST',
    '${path(a.id)}/jobs',
    (json) => ownedStatus(json, a.id),
    body: {'version': a.version},
    key: key,
  );
  Future<AnalysisView> cancel(AnalysisView a, String key) => call(
    'POST',
    '${path(a.id)}/cancel',
    (json) => ownedStatus(json, a.id),
    body: {'version': a.version},
    key: key,
  );

  Future<LeaseView> lease(AnalysisView a, String key) => call(
    'POST',
    '${path(a.id)}/jobs/${a.job.id}/lease',
    (json) {
      final result = LeaseView.fromJson(json);
      if (result.id != a.id || result.job.id != a.job.id) invalidAnalysis();
      return result;
    },
    body: {'job_version': a.job.version},
    key: key,
  );

  Future<ExtractResponse> extract(LeaseView lease, String key) => call(
    'POST',
    '${path(lease.id)}/jobs/${lease.job.id}/extract',
    (json) {
      final result = ExtractResponse.fromJson(json);
      if (result.status.id != lease.id ||
          result.status.job.id != lease.job.id ||
          (result.revision != null &&
              (result.revision!.analysisId != lease.id ||
                  result.revision!.revision != result.status.resultRevision ||
                  result.status.job.state != 'completed'))) {
        invalidAnalysis();
      }
      if (result.revision != null) observedFields(result.revision!.extraction);
      if (result.status.job.state == 'completed') {
        if (result.revision == null ||
            result.metadata == null ||
            result.error != null ||
            result.revision!.reviewStatus != 'unreviewed' ||
            result.revision!.verification.status != 'unverified') {
          invalidAnalysis();
        }
      } else if (!['failed', 'needs_input'].contains(result.status.job.state) ||
          result.revision != null ||
          result.metadata != null ||
          result.error == null ||
          ((result.status.job.state == 'needs_input') !=
              (result.error!.code == 'no_observations'))) {
        invalidAnalysis();
      }
      return result;
    },
    key: key,
    body: {
      'job_version': lease.job.version,
      'lease_token': lease.leaseToken,
      'fencing_token': lease.job.fencingToken,
    },
  );

  Future<ReviewContext> prepare(AnalysisView a, String key) => call(
    'POST',
    '${path(a.id)}/review-context',
    (json) => context(json, a.id),
    key: key,
    body: {'version': a.version, 'revision': a.resultRevision},
  );
  Future<ReviewContext> reviewContext(String id) =>
      call('GET', '${path(id)}/review-context', (json) => context(json, id));
  ReviewContext context(Map<String, dynamic> json, String id) {
    final result = ReviewContext.fromJson(json);
    if (result.analysisId != id ||
        !sameKeySet(
          result.requiredFieldKeys,
          observedFields(result.extraction).keys,
        )) {
      invalidAnalysis();
    }
    return result;
  }

  Future<ReviewReceipt> submit(String id, HumanReview body, String key) => call(
    'POST',
    '${path(id)}/reviews',
    (json) {
      final result = ReviewReceipt.fromJson(json);
      if (result.analysisId != id ||
          result.revision != body.revision ||
          result.candidateSetId != body.candidateSetId ||
          result.decision != body.decision ||
          result.version != body.version + 1 ||
          result.isFinal != (body.decision != 'unresolved')) {
        invalidAnalysis();
      }
      return result;
    },
    body: body.toJson(),
    key: key,
  );
  Future<AnalysisReport> report(String id, int revision) =>
      call('GET', '${path(id)}/report?revision=$revision', (json) {
        final result = AnalysisReport.fromJson(json);
        if (result.analysisId != id || result.revision != revision) {
          invalidAnalysis();
        }
        validateSyntheticReport(result);
        return result;
      });
}
