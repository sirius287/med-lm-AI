import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:medlm/app/app.dart';
import 'package:medlm/app/providers.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/core/config.dart';

void main() {
  testWidgets(
    'startup shows splash then home; settings navigation and theme work',
    (tester) async {
      final boot = Completer<void>();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            startupProvider.overrideWith((ref) => boot.future),
            configProvider.overrideWithValue(
              const AppConfig(apiBaseUrl: 'http://localhost:8000/api/v1'),
            ),
          ],
          child: const MedlmApp(),
        ),
      );
      expect(find.text('Opening your workspace…'), findsOneWidget);
      boot.complete();
      await tester.pumpAndSettle();
      expect(find.byType(HomeScreen), findsOneWidget);
      await tester.tap(find.byKey(const Key('settings')));
      await tester.pumpAndSettle();
      expect(find.byType(SettingsScreen), findsOneWidget);
      await tester.tap(find.byKey(const Key('theme')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Dark').last);
      await tester.pumpAndSettle();
      expect(
        Theme.of(tester.element(find.byType(SettingsScreen))).brightness,
        Brightness.dark,
      );
    },
  );

  testWidgets('Hindi and Telugu load through language selection', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [startupProvider.overrideWith((ref) async {})],
        child: const MedlmApp(),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('settings')));
    await tester.pumpAndSettle();
    for (final language in [('हिन्दी', 'दिखावट'), ('తెలుగు', 'రూపం')]) {
      await tester.tap(find.byKey(const Key('language')));
      await tester.pumpAndSettle();
      await tester.tap(find.text(language.$1).last);
      await tester.pumpAndSettle();
      expect(find.text(language.$2), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
  });

  testWidgets('failed startup offers retry and recovers', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          startupProvider.overrideWith((ref) async {
            if (calls++ == 0) throw StateError('synthetic startup failure');
          }),
        ],
        child: const MedlmApp(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Try again'), findsOneWidget);
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.byType(HomeScreen), findsOneWidget);
  });

  test(
    'API sends auth and maps errors without leaking provider detail',
    () async {
      final api = ApiClient(
        'https://example.org/api/v1',
        MockClient((request) async {
          expect(request.headers['Authorization'], 'Bearer synthetic-token');
          expect(request.headers['X-CSRF-Token'], 'synthetic-csrf');
          return http.Response(
            '{"error":{"code":"invalid_session","message":"private"}}',
            401,
          );
        }),
        accessToken: () async => 'synthetic-token',
      )..csrfToken = 'synthetic-csrf';
      await expectLater(
        api.request('GET', '/auth/session', authenticated: true),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'invalid_session'),
        ),
      );
    },
  );
}
