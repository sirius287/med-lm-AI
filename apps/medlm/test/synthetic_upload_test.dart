import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/uploads/synthetic_upload_service.dart';

const id = '11111111-1111-4111-8111-111111111111';
final hash = List.filled(64, 'a').join();

void main() {
  test(
    'synthetic flow uses authenticated same-origin paths and versioned completion',
    () async {
      final calls = <String>[];
      final api = ApiClient(
        'http://localhost/api/v1',
        MockClient((request) async {
          calls.add('${request.method} ${request.url.path}');
          expect(request.headers['Authorization'], 'Bearer synthetic-token');
          expect(request.headers['X-CSRF-Token'], 'synthetic-csrf');
          expect(request.followRedirects, false);
          if (request.url.path.endsWith('/uploads')) {
            final body = jsonDecode(request.body);
            expect(body['consent_version'], 'synthetic-v1');
            expect(body.containsKey('user_id'), false);
            return http.Response(
              jsonEncode({
                'upload_id': id,
                'ticket': 'opaque',
                'upload_url': 'https://untrusted.invalid/leak',
              }),
              201,
            );
          }
          if (request.method == 'PUT') {
            expect(request.headers['Content-Type'], 'image/png');
            expect(request.headers['X-Upload-Ticket'], 'opaque');
            expect(request.bodyBytes, [1, 2, 3]);
            return http.Response('', 204);
          }
          if (request.method == 'GET') {
            return http.Response('{"version":2}', 200);
          }
          expect(request.headers['If-Match'], '"2"');
          return http.Response('{"status":"deleting","version":4}', 200);
        }),
        accessToken: () async => 'synthetic-token',
      )..csrfToken = 'synthetic-csrf';
      final service = SyntheticUploadService(api);
      final fixture = Uint8List.fromList([1, 2, 3]);
      final result = await service.upload(
        fixture: fixture,
        checksum: hash,
        requestKey: id,
      );
      expect(result['status'], 'deleting');
      expect(calls, [
        'POST /api/v1/uploads',
        'PUT /api/v1/uploads/$id/content',
        'GET /api/v1/uploads/$id',
        'POST /api/v1/uploads/$id/complete',
      ]);
      expect(service.hasPendingBytes, false);
      expect(fixture, [1, 2, 3]); // No mutation of the caller's buffer.
    },
  );

  test(
    'logout during creation discards bytes and never sends content',
    () async {
      final response = Completer<http.Response>();
      var calls = 0;
      final service = SyntheticUploadService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient((request) {
            calls++;
            return response.future;
          }),
        ),
      );
      final pending = service.upload(
        fixture: Uint8List.fromList([1]),
        checksum: hash,
        requestKey: id,
      );
      await Future<void>.delayed(Duration.zero);
      expect(service.hasPendingBytes, true);
      service.clearSession();
      response.complete(
        http.Response(jsonEncode({'upload_id': id, 'ticket': 'opaque'}), 201),
      );
      await expectLater(
        pending,
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'upload_cancelled'),
        ),
      );
      expect(calls, 1);
      expect(service.hasPendingBytes, false);
    },
  );

  test(
    'missing ticket cannot replay content and failures clear temporary bytes',
    () async {
      final service = SyntheticUploadService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient(
            (_) async => http.Response(
              jsonEncode({'upload_id': id, 'ticket': null}),
              201,
            ),
          ),
        ),
      );
      await expectLater(
        service.upload(
          fixture: Uint8List.fromList([1]),
          checksum: hash,
          requestKey: id,
        ),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'ticket_unavailable',
          ),
        ),
      );
      expect(service.hasPendingBytes, false);
    },
  );

  test(
    '401 clears csrf and does not report successful upload or deletion',
    () async {
      final api = ApiClient(
        'http://localhost/api/v1',
        MockClient(
          (_) async =>
              http.Response('{"error":{"code":"invalid_session"}}', 401),
        ),
      )..csrfToken = 'csrf';
      final service = SyntheticUploadService(api);
      await expectLater(
        service.upload(
          fixture: Uint8List.fromList([1]),
          checksum: hash,
          requestKey: id,
        ),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)),
      );
      expect(api.csrfToken, null);
      expect(service.hasPendingBytes, false);
      await expectLater(service.delete(id, 2), throwsA(isA<ApiException>()));
    },
  );

  test(
    'deletion carries version and receipt polling never fabricates completion',
    () async {
      final methods = <String>[];
      final service = SyntheticUploadService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient((r) async {
            methods.add(r.method);
            if (r.method == 'DELETE') {
              expect(r.headers['If-Match'], '"3"');
              return http.Response('{"status":"deleting"}', 202);
            }
            return http.Response('{"receipts":[]}', 200);
          }),
        ),
      );
      expect((await service.delete(id, 3))['status'], 'deleting');
      expect((await service.receipts(id))['receipts'], isEmpty);
      expect(methods, ['DELETE', 'GET']);
    },
  );

  test(
    'preview requires no-store image response; expired and cross-owner access fail',
    () async {
      for (final status in [401, 404, 410]) {
        final service = SyntheticUploadService(
          ApiClient(
            'http://localhost/api/v1',
            MockClient((_) async => http.Response('', status)),
          ),
        );
        await expectLater(
          service.preview(id),
          throwsA(
            isA<ApiException>().having((e) => e.status, 'status', status),
          ),
        );
      }
      final service = SyntheticUploadService(
        ApiClient(
          'http://localhost/api/v1',
          MockClient(
            (_) async => http.Response.bytes(
              [1, 2],
              200,
              headers: {
                'content-type': 'image/png',
                'cache-control': 'no-store',
              },
            ),
          ),
        ),
      );
      expect(await service.preview(id), [1, 2]);
    },
  );

  test('invalid ID, redirect and header injection are rejected', () async {
    final api = ApiClient(
      'http://localhost/api/v1',
      MockClient(
        (_) async => http.Response(
          '',
          307,
          headers: {'location': 'https://elsewhere.invalid'},
        ),
      ),
    );
    final service = SyntheticUploadService(api);
    expect(
      () => service.status('../auth/session'),
      throwsA(isA<ApiException>()),
    );
    await expectLater(
      api.request('GET', '/uploads', headers: {'Authorization': 'stolen'}),
      throwsA(isA<ApiException>()),
    );
    await expectLater(
      api.request('POST', '/uploads'),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'redirect_denied'),
      ),
    );
  });
}
