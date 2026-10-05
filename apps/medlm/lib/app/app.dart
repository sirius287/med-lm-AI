import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../core/logging.dart';
import '../design_system/theme.dart';
import '../l10n/app_localizations.dart';
import 'providers.dart';
import '../auth/auth_screen.dart';
import '../auth/auth_controller.dart';
import '../medications/medication_shell.dart';
import '../medications/dashboard_screen.dart';
import '../medications/medication_list_screen.dart';
import '../medications/medication_detail_screen.dart';
import '../medications/medication_form_screen.dart';
import '../medications/history_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (_, _) => const SplashScreen()),
      GoRoute(path: '/home', builder: (_, _) => const HomeScreen()),
      GoRoute(path: '/settings', builder: (_, _) => const SettingsScreen()),
      GoRoute(path: '/account', builder: (_, _) => const AuthScreen()),
      GoRoute(
        path: '/medications',
        builder: (_, _) => const MedicationShell(child: MedicationListScreen()),
      ),
      GoRoute(
        path: '/medications/new',
        builder: (_, _) => const MedicationShell(child: MedicationFormScreen()),
      ),
      GoRoute(
        path: '/medications/:id',
        builder: (_, state) => MedicationShell(
          child: MedicationDetailScreen(id: state.pathParameters['id']!),
        ),
      ),
      GoRoute(
        path: '/medications/:id/edit',
        builder: (_, state) => MedicationShell(
          child: MedicationFormScreen(id: state.pathParameters['id']!),
        ),
      ),
      GoRoute(
        path: '/history',
        builder: (_, _) => const MedicationShell(child: HistoryScreen()),
      ),
    ],
    errorBuilder: (context, _) => Scaffold(
      appBar: AppBar(title: Text(AppLocalizations.of(context)!.notFound)),
      body: Center(
        child: FilledButton(
          onPressed: () => context.go('/home'),
          child: Text(AppLocalizations.of(context)!.home),
        ),
      ),
    ),
  );
  ref.onDispose(router.dispose);
  return router;
});

class MedlmApp extends ConsumerWidget {
  const MedlmApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => MaterialApp.router(
    debugShowCheckedModeBanner: false,
    title: 'MedLM AI',
    theme: MedlmTheme.create(Brightness.light),
    darkTheme: MedlmTheme.create(Brightness.dark),
    themeMode: ref.watch(themeModeProvider),
    locale: ref.watch(localeProvider),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    routerConfig: ref.watch(routerProvider),
  );
}

class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = AppLocalizations.of(context)!;
    final startup = ref.watch(startupProvider);
    ref.listen(startupProvider, (_, next) {
      if (next.hasValue) {
        ref.read(accountProvider).restore();
        context.go('/home');
      }
      if (next.hasError) AppLog.startupFailed();
    });
    if (startup.hasValue) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (context.mounted) {
          ref.read(accountProvider).restore();
          context.go('/home');
        }
      });
    }
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.health_and_safety_outlined, size: 64),
                const SizedBox(height: 24),
                Text(
                  s.appTitle,
                  style: Theme.of(context).textTheme.headlineLarge,
                ),
                const SizedBox(height: 16),
                Text(startup.hasError ? s.startupFailed : s.starting),
                if (startup.hasError)
                  FilledButton(
                    onPressed: () => ref.invalidate(startupProvider),
                    child: Text(s.retry),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = AppLocalizations.of(context)!;
    if (ref.watch(accountProvider).status == AccountStatus.signedIn) {
      return const MedicationShell(child: DashboardScreen());
    }
    return Scaffold(
      appBar: AppBar(
        title: Text(s.appTitle),
        actions: [
          IconButton(
            key: const Key('settings'),
            tooltip: s.settings,
            onPressed: () => context.push('/settings'),
            icon: const Icon(Icons.settings_outlined),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(24),
            children: [
              SoftPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.health_and_safety_outlined,
                      size: 48,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(height: 24),
                    Text(
                      s.welcome,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 16),
                    Text(s.intro, style: Theme.of(context).textTheme.bodyLarge),
                    const SizedBox(height: 24),
                    Text(s.onlineNotice),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      key: const Key('account'),
                      onPressed: () => context.push('/account'),
                      icon: const Icon(Icons.person_outline),
                      label: Text(s.account),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});
  @override
  ConsumerState<SettingsScreen> createState() => _SettingsState();
}

class _SettingsState extends ConsumerState<SettingsScreen> {
  bool? connected;
  bool busy = false;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    return Scaffold(
      appBar: AppBar(title: Text(s.settings)),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              DropdownButtonFormField<ThemeMode>(
                key: const Key('theme'),
                initialValue: ref.watch(themeModeProvider),
                decoration: InputDecoration(labelText: s.theme),
                isExpanded: true,
                items: [
                  DropdownMenuItem(
                    value: ThemeMode.system,
                    child: Text(s.system),
                  ),
                  DropdownMenuItem(
                    value: ThemeMode.light,
                    child: Text(s.light),
                  ),
                  DropdownMenuItem(value: ThemeMode.dark, child: Text(s.dark)),
                ],
                onChanged: (value) {
                  if (value != null) {
                    ref.read(themeModeProvider.notifier).state = value;
                  }
                },
              ),
              const SizedBox(height: 24),
              DropdownButtonFormField<String>(
                key: const Key('language'),
                initialValue: ref.watch(localeProvider).languageCode,
                decoration: InputDecoration(labelText: s.language),
                isExpanded: true,
                items: const [
                  DropdownMenuItem(value: 'en', child: Text('English')),
                  DropdownMenuItem(value: 'hi', child: Text('हिन्दी')),
                  DropdownMenuItem(value: 'te', child: Text('తెలుగు')),
                ],
                onChanged: (value) {
                  if (value != null) {
                    ref.read(localeProvider.notifier).state = Locale(
                      value,
                      'IN',
                    );
                  }
                },
              ),
              const SizedBox(height: 24),
              OutlinedButton(
                onPressed: busy
                    ? null
                    : () async {
                        setState(() {
                          busy = true;
                          connected = null;
                        });
                        bool success;
                        try {
                          final response = await ref.read(apiProvider).health();
                          success = response['status'] == 'ok';
                        } catch (_) {
                          success = false;
                        }
                        if (mounted) {
                          setState(() {
                            connected = success;
                            busy = false;
                          });
                        }
                      },
                child: Text(s.checkConnection),
              ),
              if (connected != null)
                Semantics(
                  liveRegion: true,
                  child: Text(connected! ? s.connected : s.connectionFailed),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
