import 'dart:async';
import 'dart:convert';
import 'package:http/testing.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/analysis/analysis_validation.dart';
import 'package:medlm/analysis/generated/analysis_models.dart';
import 'package:medlm/analysis/generated/synthetic_fixture_catalog.dart';
import 'package:medlm/analysis/synthetic_analysis_service.dart';

const analysisId = '10000000-0000-4000-8000-000000000001';
const jobId = '10000000-0000-4000-8000-000000000002';
const candidateSetId = '10000000-0000-4000-8000-000000000003';
const firstLineId = '10000000-0000-4000-8000-000000000004';
const secondLineId = '10000000-0000-4000-8000-000000000005';
const leaseToken = '10000000-0000-4000-8000-000000000006';
const reviewId = '10000000-0000-4000-8000-000000000007';
const futureDeadline = '2099-10-15T10:00:00Z';

Map<String, dynamic> observation(String? text, {bool ambiguous = false}) => {
  'raw_text': text,
  'normalized_value': text,
  'unit': null,
  'bounding_box': null,
  'ambiguity_reason': ambiguous ? 'Synthetic ambiguity' : null,
  'alternatives': ambiguous ? ['TEST ITEM B'] : <String>[],
  'confidence': null,
};

Map<String, dynamic> observationSet({
  bool prescription = false,
  bool ambiguous = false,
}) {
  if (!prescription) {
    return {
      'document_kind': 'box',
      'lines': <dynamic>[],
      'medicine': {
        for (final key in medicineObservationKeys)
          key: observation(
            key == 'medicine' ? ' TEST ITEM A ' : null,
            ambiguous: key == 'medicine' && ambiguous,
          ),
      },
    };
  }
  return {
    'document_kind': 'prescription',
    'medicine': null,
    'lines': [
      for (final (ordinal, id) in [(0, firstLineId), (1, secondLineId)])
        {
          'line_id': id,
          'ordinal': ordinal,
          'fields': {
            for (final key in prescriptionObservationKeys)
              key: observation(
                key == 'medicine'
                    ? 'TEST LINE $ordinal'
                    : key == 'strength' && ordinal == 0
                    ? 'STRENGTH TOKEN'
                    : null,
              ),
          },
        },
    ],
  };
}

Map<String, dynamic> statusJson({
  String state = 'queued',
  int version = 1,
  int jobVersion = 1,
  int? revision,
  String availability = 'available',
  int attempt = 1,
}) => {
  'id': analysisId,
  'version': version,
  'availability': availability,
  'expires_at': futureDeadline,
  'expired_at': availability == 'expired' ? '2026-10-15T10:00:00Z' : null,
  'result_revision': revision,
  'job': {
    'id': jobId,
    'attempt': attempt,
    'state': state,
    'version': jobVersion,
    'fencing_token': 1,
    'lease_expires_at': futureDeadline,
  },
};

Map<String, dynamic> reportJson({
  bool prescription = false,
  bool ambiguous = false,
}) {
  final fixture = bundledFixtures.firstWhere(
    (f) => f.kind == (prescription ? 'prescription' : 'box'),
  );
  return {
    'schema_version': 1,
    'assembler_version': 'synthetic-report-v1',
    'analysis_id': analysisId,
    'analysis_version': 2,
    'extraction_revision_id': '10000000-0000-4000-8000-000000000008',
    'revision': 1,
    'country': 'IN',
    'locale': 'en-IN',
    'observations': observationSet(
      prescription: prescription,
      ambiguous: ambiguous,
    ),
    'provenance': {
      'mode': 'synthetic',
      'fixture_id': fixture.id,
      'source_sha256': fixture.originalHash,
    },
    'extraction_metadata': {
      'provider_id': 'synthetic',
      'model_id': 'deterministic-v1',
      'pipeline_version': 'synthetic-extraction-v1',
      'fixture_revision': 1,
      'sanitized_sha256': fixture.sanitizedHash,
    },
    'purpose': 'synthetic_test_not_medical',
    'review_state': 'unreviewed',
    'review_history': <dynamic>[],
    'accepted_transcription': <String, dynamic>{},
    'observation_conflicts': ambiguous
        ? [
            {
              'field_key': 'medicine',
              'raw_text': ' TEST ITEM A ',
              'alternatives': ['TEST ITEM B'],
              'ambiguity_reason': 'Synthetic ambiguity',
            },
          ]
        : <dynamic>[],
    'fields': {
      for (final key in medicalInformationKeys)
        key: {
          'status': 'unavailable',
          'value': null,
          'reason': 'no_authoritative_source_checked',
          'evidence_refs': <String>[],
        },
    },
    'evidence': <dynamic>[],
    'verification_status': 'unverified',
    'product_id': null,
    'verified_at': null,
    'source_checked_at': null,
    'image_available': true,
    'original_expires_at': futureDeadline,
    'cancelled': false,
    'expired': false,
  };
}

Map<String, dynamic> contextJson({bool prescription = false}) => {
  'analysis_id': analysisId,
  'version': 2,
  'revision': 1,
  'candidate_set_id': candidateSetId,
  'candidates': <dynamic>[],
  'extraction': observationSet(prescription: prescription),
  'required_field_keys': prescription
      ? [
          for (final id in [firstLineId, secondLineId])
            for (final key in prescriptionObservationKeys) '$id.$key',
        ]
      : medicineObservationKeys,
  'closed': false,
  'image_available': true,
  'expires_at': futureDeadline,
  'verification': {'status': 'unverified', 'verified_at': null},
  'history': <dynamic>[],
};

/// Explicit test double only. No provider/network/database or production registration.
class FakeAnalysisService extends SyntheticAnalysisService {
  FakeAnalysisService()
    : super(
        ApiClient(
          'https://synthetic.invalid/api/v1',
          MockClient(
            (_) async => throw StateError('Unexpected network request'),
          ),
        ),
      );
  Map<String, dynamic> currentStatus = statusJson();
  Map<String, dynamic> currentReport = reportJson();
  Map<String, dynamic> currentContext = contextJson();
  final calls = <String>[];
  final requestKeys = <String, List<String>>{};
  final bodies = <Map<String, dynamic>>[];
  final receipts = <String, ReviewReceipt>{};
  final failures = <String, ApiException>{};
  Completer<void>? extracting;
  Completer<void>? reporting;
  bool prepared = false, cleared = false, loseReviewReceipt = false;
  String extractionState = 'completed';
  void hit(String operation, [String? key]) {
    calls.add(operation);
    if (key != null) requestKeys.putIfAbsent(operation, () => []).add(key);
    final failure = failures.remove(operation);
    if (failure != null) throw failure;
  }

  @override
  void clearSession() {
    cleared = true;
    super.clearSession();
  }

  @override
  Future<String> upload(BundledFixture fixture, String key) async {
    hit('upload', key);
    final prescription = fixture.kind == 'prescription';
    currentReport = reportJson(
      prescription: prescription,
      ambiguous: fixture.id.contains('_ambiguous'),
    );
    currentContext = contextJson(prescription: prescription);
    currentContext['extraction'] = currentReport['observations'];
    currentReport['provenance']['fixture_id'] = fixture.id;
    currentReport['provenance']['source_sha256'] = fixture.originalHash;
    currentReport['extraction_metadata']['sanitized_sha256'] =
        fixture.sanitizedHash;
    return analysisId;
  }

  @override
  Future<AnalysisView> create(
    String uploadId,
    BundledFixture fixture,
    String locale,
    String key,
  ) async {
    hit('create', key);
    return AnalysisView.fromJson(currentStatus);
  }

  @override
  Future<AnalysisView> status(String id) async {
    hit('status');
    return AnalysisView.fromJson(currentStatus);
  }

  @override
  Future<LeaseView> lease(AnalysisView a, String key) async {
    hit('lease', key);
    return LeaseView.fromJson({...currentStatus, 'lease_token': leaseToken});
  }

  @override
  Future<ExtractResponse> extract(LeaseView a, String key) async {
    hit('extract', key);
    await extracting?.future;
    currentStatus = {
      ...currentStatus,
      'version': currentReport['analysis_version'],
      'result_revision': extractionState == 'completed'
          ? currentReport['revision']
          : null,
      'job': <String, dynamic>{
        ...currentStatus['job'],
        'state': extractionState,
      },
    };
    return ExtractResponse.fromJson({
      'status': currentStatus,
      'revision': extractionState == 'completed'
          ? {
              'analysis_id': analysisId,
              'revision': currentReport['revision'],
              'extraction': currentReport['observations'],
              'provenance': currentReport['provenance'],
              'verification': {'status': 'unverified', 'verified_at': null},
              'review_status': 'unreviewed',
            }
          : null,
      'metadata': extractionState == 'completed'
          ? currentReport['extraction_metadata']
          : null,
      'error': extractionState == 'completed'
          ? null
          : {
              'code': extractionState == 'needs_input'
                  ? 'no_observations'
                  : 'adapter_failure',
              'message': 'Synthetic test failure',
            },
    });
  }

  @override
  Future<AnalysisView> newAttempt(AnalysisView a, String key) async {
    hit('newAttempt', key);
    prepared = false;
    currentStatus = {
      ...currentStatus,
      'version': a.version + 1,
      'job': <String, dynamic>{
        ...currentStatus['job'],
        'id': '20000000-0000-4000-8000-000000000002',
        'state': 'queued',
        'attempt': a.job.attempt + 1,
      },
    };
    currentReport =
        jsonDecode(jsonEncode(currentReport)) as Map<String, dynamic>;
    currentReport['analysis_version'] = a.version + 2;
    currentReport['revision'] = (a.resultRevision ?? 0) + 1;
    currentReport['review_history'] = <dynamic>[];
    currentReport['review_state'] = 'unreviewed';
    currentReport['accepted_transcription'] = <String, dynamic>{};
    currentContext = {
      ...currentContext,
      'version': a.version + 2,
      'revision': currentReport['revision'],
      'closed': false,
      'history': <dynamic>[],
    };
    return AnalysisView.fromJson(currentStatus);
  }

  @override
  Future<AnalysisView> cancel(AnalysisView a, String key) async {
    hit('cancel', key);
    currentStatus = {
      ...currentStatus,
      'version': a.version + 1,
      'availability': 'cancelled',
    };
    currentReport = {
      ...currentReport,
      'analysis_version': a.version + 1,
      'cancelled': true,
      'image_available': false,
    };
    currentContext = {
      ...currentContext,
      'version': a.version + 1,
      'image_available': false,
    };
    return AnalysisView.fromJson(currentStatus);
  }

  @override
  Future<ReviewContext> prepare(AnalysisView a, String key) async {
    hit('prepare', key);
    prepared = true;
    return ReviewContext.fromJson(currentContext);
  }

  @override
  Future<ReviewContext> reviewContext(String id) async {
    hit('reviewContext');
    if (!prepared) throw const ApiException('review_not_prepared', status: 409);
    return ReviewContext.fromJson(currentContext);
  }

  @override
  Future<AnalysisReport> report(String id, int revision) async {
    hit('report');
    await reporting?.future;
    return AnalysisReport.fromJson(currentReport);
  }

  @override
  Future<ReviewReceipt> submit(String id, HumanReview body, String key) async {
    hit('submit', key);
    bodies.add(body.toJson());
    if (receipts.containsKey(key)) return receipts[key]!;
    final accepted = validateHumanReview(
      body,
      ExtractionResult.fromJson(currentReport['observations']),
    );
    final receipt = ReviewReceipt.fromJson({
      'id': reviewId,
      'analysis_id': id,
      'revision': body.revision,
      'candidate_set_id': body.candidateSetId,
      'version': body.version + 1,
      'decision': body.decision,
      'final': body.decision != 'unresolved',
      'created_at': '2026-10-15T10:00:00Z',
      'verification': {'status': 'unverified', 'verified_at': null},
      'accepted_values': accepted,
    });
    receipts[key] = receipt;
    currentStatus = {
      ...currentStatus,
      'version': body.version + 1,
      'availability': receipt.isFinal ? 'unavailable' : 'available',
    };
    currentReport = {
      ...currentReport,
      'analysis_version': body.version + 1,
      'review_state': body.decision,
      'accepted_transcription': accepted,
      'image_available': !receipt.isFinal,
      'review_history': [
        ...currentReport['review_history'],
        {'id': reviewId, 'review': body.toJson()},
      ],
    };
    currentContext = {
      ...currentContext,
      'version': body.version + 1,
      'closed': receipt.isFinal,
      'image_available': !receipt.isFinal,
      'history': [...currentContext['history'], receipt.toJson()],
    };
    if (loseReviewReceipt) {
      loseReviewReceipt = false;
      throw const ApiException('connection_failed');
    }
    return receipt;
  }
}
