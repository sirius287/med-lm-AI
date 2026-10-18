import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/analysis/generated/analysis_models.dart';
import 'package:medlm/analysis/generated/synthetic_fixture_catalog.dart';
import 'package:medlm/analysis/synthetic_analysis_service.dart';
import 'analysis_test_support.dart';

void main() {
  test(
    'inconsistent terminal response cannot claim completed extraction',
    () async {
      final lease = LeaseView.fromJson({
        ...statusJson(),
        'lease_token': leaseToken,
      });
      for (final state in ['completed', 'queued']) {
        final service = SyntheticAnalysisService(
          ApiClient(
            'http://localhost/api/v1',
            MockClient(
              (_) async => http.Response(
                jsonEncode({
                  'status': statusJson(state: state),
                  'revision': null,
                  'metadata': null,
                  'error': null,
                }),
                200,
              ),
            ),
          ),
        );
        await expectLater(
          service.extract(lease, reviewId),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test(
    'analysis transport reuses auth/CSRF and sends no fixture/provider/owner overrides',
    () async {
      final requests = <http.Request>[];
      final api = ApiClient(
        'http://localhost/api/v1',
        MockClient((r) async {
          requests.add(r);
          expect(r.headers['Authorization'], 'Bearer synthetic-token');
          expect(r.headers['X-CSRF-Token'], 'synthetic-csrf');
          expect(r.followRedirects, isFalse);
          return http.Response(jsonEncode(statusJson()), 201);
        }),
        accessToken: () async => 'synthetic-token',
      )..csrfToken = 'synthetic-csrf';
      final service = SyntheticAnalysisService(api);
      await service.create(analysisId, bundledFixtures[3], 'te-IN', leaseToken);
      final body = jsonDecode(requests.single.body) as Map;
      expect(body.keys.toSet(), {
        'upload_id',
        'document_kind',
        'content_type',
        'retain_for_review',
        'locale',
      });
      expect(body['retain_for_review'], isTrue);
      expect(body['locale'], 'te-IN');
      expect(requests.single.headers['Idempotency-Key'], leaseToken);
    },
  );
  test(
    'ticketless replay completes existing immutable content without a second PUT',
    () async {
      final methods = <String>[];
      final service = SyntheticAnalysisService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient((r) async {
            methods.add(r.method);
            if (r.url.path.endsWith('/uploads')) {
              return http.Response(
                jsonEncode({'upload_id': analysisId, 'ticket': null}),
                201,
              );
            }
            if (r.method == 'GET') {
              return http.Response('{"status":"initiated","version":1}', 200);
            }
            expect(
              jsonDecode(r.body)['checksum_sha256'],
              bundledFixtures[3].originalHash,
            );
            return http.Response(
              jsonEncode({'upload_id': analysisId, 'status': 'accepted'}),
              200,
            );
          }),
        ),
      );
      expect(await service.upload(bundledFixtures[3], leaseToken), analysisId);
      expect(methods, ['POST', 'GET', 'POST']);
      expect(service.uploads.hasPendingBytes, isFalse);
    },
  );
  test(
    'ticketless accepted replay reads status without resubmitting content',
    () async {
      var writes = 0;
      final service = SyntheticAnalysisService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient((r) async {
            if (r.method == 'POST') {
              writes++;
              return http.Response(
                jsonEncode({'upload_id': analysisId, 'ticket': null}),
                201,
              );
            }
            return http.Response(
              jsonEncode({'upload_id': analysisId, 'status': 'accepted'}),
              200,
            );
          }),
        ),
      );
      expect(await service.upload(bundledFixtures[3], leaseToken), analysisId);
      expect(writes, 1);
    },
  );
  test(
    'foreign response, unsupported medical value and inconsistent conflict fail closed',
    () async {
      final invalid = [
        reportJson()..['analysis_id'] = jobId,
        reportJson()..['accepted_transcription'] = {'medicine': 'invented'},
        reportJson()
          ..['observation_conflicts'] = [
            {
              'field_key': 'medicine',
              'raw_text': 'other',
              'alternatives': ['other'],
              'ambiguity_reason': 'invented',
            },
          ],
        reportJson()..['fields'].remove('strength'),
      ];
      for (final data in invalid) {
        final service = SyntheticAnalysisService(
          ApiClient(
            'http://localhost/api/v1',
            MockClient((_) async => http.Response(jsonEncode(data), 200)),
          ),
        );
        await expectLater(
          service.report(analysisId, 1),
          throwsA(
            isA<ApiException>().having(
              (e) => e.code,
              'code',
              'invalid_response',
            ),
          ),
        );
      }
    },
  );
  test(
    'report remains text-only after image expiry and does not fetch preview',
    () async {
      final data = reportJson()
        ..['expired'] = true
        ..['image_available'] = false;
      final service = SyntheticAnalysisService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient((r) async {
            expect(r.url.path, '/api/v1/analyses/$analysisId/report');
            return http.Response(jsonEncode(data), 200);
          }),
        ),
      );
      expect((await service.report(analysisId, 1)).expired, isTrue);
    },
  );
  test(
    'malformed IDs and mismatched required field coverage are rejected',
    () async {
      var calls = 0;
      final data = contextJson()..['required_field_keys'] = ['medicine'];
      final service = SyntheticAnalysisService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient((_) async {
            calls++;
            return http.Response(jsonEncode(data), 200);
          }),
        ),
      );
      expect(
        () => service.status('../auth/session'),
        throwsA(isA<ApiException>()),
      );
      expect(calls, 0);
      await expectLater(
        service.reviewContext(analysisId),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test(
    'lease/extraction payload is limited to the current server-issued lease',
    () async {
      final lease = LeaseView.fromJson({
        ...statusJson(),
        'lease_token': leaseToken,
      });
      final service = SyntheticAnalysisService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient((r) async {
            expect(jsonDecode(r.body), {
              'job_version': 1,
              'lease_token': leaseToken,
              'fencing_token': 1,
            });
            return http.Response(
              jsonEncode({
                'status': statusJson(state: 'needs_input'),
                'revision': null,
                'metadata': null,
                'error': {'code': 'no_observations', 'message': 'No text'},
              }),
              200,
            );
          }),
        ),
      );
      expect((await service.extract(lease, reviewId)).revision, isNull);
    },
  );
}
