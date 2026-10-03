import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/app/app.dart';
import 'package:medlm/app/providers.dart';
import 'package:medlm/auth/auth_controller.dart';
import 'package:medlm/auth/auth_screen.dart';
import 'package:medlm/core/api_client.dart';
import 'package:medlm/design_system/theme.dart';
import 'package:medlm/l10n/app_localizations.dart';
import 'auth_controller_test.dart' show SyntheticAuth;

Future<void> showAccount(
  WidgetTester tester,
  SyntheticAuth auth, {
  String language = 'en',
  Brightness brightness = Brightness.light,
  double scale = 1,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        accountProvider.overrideWith(
          (ref) => AuthController(auth, initialize: () async {}),
        ),
      ],
      child: MaterialApp(
        theme: MedlmTheme.create(brightness),
        locale: Locale(language, 'IN'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(scale)),
          child: child!,
        ),
        home: const AuthScreen(),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('registration and rate-limit errors use accurate messages', (
    tester,
  ) async {
    final auth = SyntheticAuth();
    await showAccount(tester, auth);
    await tester.ensureVisible(find.byKey(const Key('toggle-auth')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('toggle-auth')));
    await tester.pumpAndSettle();
    for (final status in [422, 429]) {
      auth.failure = ApiException('private', status: status);
      await tester.enterText(
        find.byKey(const Key('email')),
        'test@example.org',
      );
      await tester.enterText(
        find.byKey(const Key('password')),
        'synthetic-password',
      );
      await tester.ensureVisible(find.byKey(const Key('submit-auth')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('submit-auth')));
      await tester.pumpAndSettle();
      final s = AppLocalizations.of(tester.element(find.byType(AuthScreen)))!;
      expect(
        find.text(status == 422 ? s.registrationFailed : s.authRateLimited),
        findsOneWidget,
      );
      expect(find.text(s.authFailed), findsNothing);
      expect(find.textContaining('Wait a minute'), findsNothing);
    }
  });

  testWidgets(
    'account re-entry and resume revalidate instead of trusting cached UI',
    (tester) async {
      final auth = SyntheticAuth()..user = 'synthetic-user';
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            startupProvider.overrideWith((ref) async {}),
            accountProvider.overrideWith(
              (ref) => AuthController(auth, initialize: () async {}),
            ),
          ],
          child: const MedlmApp(),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('account')));
      await tester.pumpAndSettle();
      expect(find.text('Signed in'), findsOneWidget);
      final container = ProviderScope.containerOf(
        tester.element(find.byType(AuthScreen)),
      );
      container.read(routerProvider).pop();
      await tester.pumpAndSettle();
      auth.user = null;
      await tester.tap(find.byKey(const Key('account')));
      await tester.pumpAndSettle();
      expect(find.text('Signed in'), findsNothing);
      expect(find.textContaining('Your session has ended'), findsOneWidget);
      auth.user = 'synthetic-user';
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(find.text('Signed in'), findsOneWidget);
      auth.failure = const ApiException('unavailable', status: 503);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(find.text('Signed in'), findsNothing);
      expect(container.read(accountProvider).status, AccountStatus.unavailable);
    },
  );

  testWidgets('home account navigation preserves existing settings route', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          startupProvider.overrideWith((ref) async {}),
          accountProvider.overrideWith(
            (ref) => AuthController(SyntheticAuth(), initialize: () async {}),
          ),
        ],
        child: const MedlmApp(),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('account')));
    await tester.pumpAndSettle();
    expect(find.byType(AuthScreen), findsOneWidget);
    await tester.tap(find.byTooltip('Home'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('settings')));
    await tester.pumpAndSettle();
    expect(find.byType(SettingsScreen), findsOneWidget);
  });
  testWidgets('form validation, obscuring, login and password clearing', (
    tester,
  ) async {
    final auth = SyntheticAuth();
    await showAccount(tester, auth);
    await tester.ensureVisible(find.byKey(const Key('submit-auth')));
    await tester.tap(find.byKey(const Key('submit-auth')));
    await tester.pumpAndSettle();
    expect(auth.logins, 0);
    expect(find.text('Enter a valid email address.'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('email')), 'test@example.org');
    await tester.enterText(
      find.byKey(const Key('password')),
      'synthetic-password',
    );
    expect(
      tester
          .widget<TextField>(
            find.descendant(
              of: find.byKey(const Key('password')),
              matching: find.byType(TextField),
            ),
          )
          .obscureText,
      true,
    );
    await tester.ensureVisible(find.byKey(const Key('submit-auth')));
    await tester.tap(find.byKey(const Key('submit-auth')));
    await tester.pumpAndSettle();
    expect(auth.logins, 1);
    expect(find.text('Signed in'), findsOneWidget);
    expect(find.byKey(const Key('password')), findsNothing);
  });
  testWidgets(
    'email keyboard next focuses password; background clears password',
    (tester) async {
      await showAccount(tester, SyntheticAuth());
      await tester.enterText(
        find.byKey(const Key('email')),
        'test@example.org',
      );
      await tester.testTextInput.receiveAction(TextInputAction.next);
      await tester.pump();
      final password = tester.widget<TextField>(
        find.descendant(
          of: find.byKey(const Key('password')),
          matching: find.byType(TextField),
        ),
      );
      expect(password.focusNode!.hasFocus, true);
      await tester.enterText(
        find.byKey(const Key('password')),
        'synthetic-password',
      );
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      await tester.pump();
      expect(password.controller!.text, isEmpty);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
    },
  );
  testWidgets('registration confirmation and failed logout remain honest', (
    tester,
  ) async {
    final auth = SyntheticAuth();
    await showAccount(tester, auth);
    await tester.ensureVisible(find.byKey(const Key('toggle-auth')));
    await tester.tap(find.byKey(const Key('toggle-auth')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('email')), 'test@example.org');
    await tester.enterText(
      find.byKey(const Key('password')),
      'synthetic-password',
    );
    await tester.ensureVisible(find.byKey(const Key('submit-auth')));
    await tester.tap(find.byKey(const Key('submit-auth')));
    await tester.pumpAndSettle();
    expect(auth.registrations, 1);
    expect(find.textContaining('If registration is accepted'), findsOneWidget);
    expect(find.text('Signed in'), findsNothing);
    await tester.pumpWidget(const SizedBox());
    auth.user = 'synthetic-user';
    await showAccount(tester, auth);
    auth.failure = const ApiException('private-server-detail', status: 503);
    await tester.tap(find.byKey(const Key('logout')));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Sign-out could not be confirmed.'),
      findsOneWidget,
    );
    expect(find.textContaining('private-server-detail'), findsNothing);
    expect(find.byKey(const Key('retry-logout')), findsOneWidget);
    expect(find.byKey(const Key('password')), findsNothing);
  });
  testWidgets('keyboard traversal reaches visible password control', (
    tester,
  ) async {
    await showAccount(tester, SyntheticAuth());
    await tester.tap(find.byKey(const Key('email')));
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    final password = tester.widget<TextField>(
      find.descendant(
        of: find.byKey(const Key('password')),
        matching: find.byType(TextField),
      ),
    );
    expect(password.focusNode!.hasFocus, true);
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    expect(find.byTooltip('Hide password'), findsOneWidget);
  });

  for (final language in ['en', 'hi', 'te']) {
    for (final brightness in Brightness.values) {
      for (final state in [
        'signedIn',
        'unavailable',
        'logoutUnconfirmed',
        'localSignOut',
        'expired',
      ]) {
        testWidgets(
          '$language $brightness $state large-text semantics and recovery controls',
          (tester) async {
            tester.view.physicalSize = const Size(360, 800);
            tester.view.devicePixelRatio = 1;
            addTearDown(tester.view.resetPhysicalSize);
            addTearDown(tester.view.resetDevicePixelRatio);
            final semantics = tester.ensureSemantics();
            try {
              final auth = SyntheticAuth()..user = 'synthetic-user';
              await showAccount(
                tester,
                auth,
                language: language,
                brightness: brightness,
                scale: 2,
              );
              final element = tester.element(find.byType(AuthScreen));
              final controller = ProviderScope.containerOf(
                element,
              ).read(accountProvider);
              final s = AppLocalizations.of(element)!;
              String expected = s.sessionVerified;
              if (state == 'unavailable') {
                auth.failure = const ApiException('unavailable', status: 503);
                await controller.restore();
                expected = s.sessionUnavailable;
              } else if (state == 'logoutUnconfirmed') {
                auth.failure = const ApiException('unavailable', status: 503);
                await controller.logout();
                expected = s.logoutUnconfirmed;
              } else if (state == 'localSignOut') {
                auth.failure = const ApiException('native_logout_unconfirmed');
                await controller.logout();
                expected = s.remoteLogoutUnconfirmed;
              } else if (state == 'expired') {
                auth.user = null;
                await controller.restore();
                expected = s.sessionExpired;
              }
              await tester.pumpAndSettle();
              expect(find.text(expected), findsOneWidget);
              await tester.ensureVisible(find.text(expected));
              await tester.pumpAndSettle();
              expect(tester.takeException(), isNull);
              await expectLater(
                tester,
                meetsGuideline(labeledTapTargetGuideline),
              );
              await expectLater(tester, meetsGuideline(textContrastGuideline));
              final control = find.byKey(
                Key(
                  state == 'signedIn'
                      ? 'logout'
                      : state == 'logoutUnconfirmed'
                      ? 'retry-logout'
                      : 'submit-auth',
                ),
              );
              if (state != 'unavailable') {
                await tester.ensureVisible(control);
                await tester.pumpAndSettle();
                expect(
                  tester.getSize(control).height,
                  greaterThanOrEqualTo(48),
                );
              }
              if (state == 'logoutUnconfirmed') {
                auth.failure = null;
                await tester.tap(control);
                await tester.pumpAndSettle();
                expect(controller.status, AccountStatus.signedOut);
              }
              if (state == 'unavailable') {
                final retry = find.text(s.retry);
                await tester.ensureVisible(retry);
                await tester.pumpAndSettle();
                auth.failure = null;
                await tester.tap(retry);
                await tester.pumpAndSettle();
                expect(controller.status, AccountStatus.signedIn);
              }
              expect(tester.takeException(), isNull);
            } finally {
              semantics.dispose();
            }
          },
        );
      }
      testWidgets('$language $brightness 200% narrow layout remains operable', (
        tester,
      ) async {
        tester.view.physicalSize = const Size(360, 800);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        await showAccount(
          tester,
          SyntheticAuth(),
          language: language,
          brightness: brightness,
          scale: 2,
        );
        await tester.ensureVisible(find.byKey(const Key('submit-auth')));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('submit-auth')));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        await tester.ensureVisible(find.byKey(const Key('toggle-auth')));
        expect(
          tester.getSize(find.byKey(const Key('submit-auth'))).height,
          greaterThanOrEqualTo(48),
        );
        final s = AppLocalizations.of(tester.element(find.byType(AuthScreen)))!;
        expect(find.text(s.emailInvalid), findsOneWidget);
      });
      testWidgets('$language $brightness accessibility guidelines', (
        tester,
      ) async {
        tester.view.physicalSize = const Size(1000, 1200);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final semantics = tester.ensureSemantics();
        try {
          await showAccount(
            tester,
            SyntheticAuth(),
            language: language,
            brightness: brightness,
          );
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
          await expectLater(tester, meetsGuideline(textContrastGuideline));
        } finally {
          semantics.dispose();
        }
      });
    }
  }
}
