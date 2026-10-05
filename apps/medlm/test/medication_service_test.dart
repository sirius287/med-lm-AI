import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/medications/medication_service.dart';
import 'manual_test_support.dart';

void main() {
  test(
    'medication transport retains bearer CSRF and retry preconditions',
    () async {
      final requests = <http.Request>[];
      final client = MockClient((request) async {
        requests.add(request);
        return http.Response(
          jsonEncode({
            'error': {'code': 'stale_version'},
          }),
          412,
        );
      });
      final api = ApiClient(
        'https://synthetic.invalid/api/v1',
        client,
        accessToken: () async => 'synthetic-token',
      )..csrfToken = 'synthetic-csrf';
      final service = MedicationService(api);
      await expectLater(
        service.save(
          {'display_name': 'Synthetic', 'dose_text': 'Literal'},
          requestId(),
          existing: syntheticMedication,
        ),
        throwsA(isA<ApiException>().having((e) => e.status, 'status', 412)),
      );
      expect(requests.single.method, 'PATCH');
      expect(requests.single.headers['If-Match'], '"1"');
      expect(
        requests.single.headers['Authorization'],
        'Bearer synthetic-token',
      );
      expect(requests.single.headers['X-CSRF-Token'], 'synthetic-csrf');
      client.close();
    },
  );
  test('list follows cursor and preserves literal unverified fields', () async {
    var calls = 0;
    final client = MockClient((request) async {
      calls++;
      if (calls == 2) expect(request.url.queryParameters['cursor'], 'opaque');
      return http.Response(
        jsonEncode({'items': [], 'next_cursor': calls == 1 ? 'opaque' : null}),
        200,
      );
    });
    expect(
      await MedicationService(
        ApiClient('https://synthetic.invalid', client),
      ).list(),
      isEmpty,
    );
    expect(calls, 2);
    client.close();
  });
  test(
    'dose event carries explicit version time and correction identity',
    () async {
      final key = requestId();
      final client = MockClient((request) async {
        final body = jsonDecode(request.body);
        expect(body['event_id'], key);
        expect(body['expected_version'], 1);
        expect(body['type'], 'taken');
        expect(body.containsKey('corrected_status'), isFalse);
        expect(request.headers['Idempotency-Key'], key);
        return http.Response('{}', 201);
      });
      await MedicationService(
        ApiClient('https://synthetic.invalid', client),
      ).event(syntheticDose, 'taken', key, at: DateTime.utc(2026, 10, 5));
      client.close();
    },
  );
}
