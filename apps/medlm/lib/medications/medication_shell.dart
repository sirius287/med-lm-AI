import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../app/providers.dart';
import '../auth/auth_controller.dart';
import '../l10n/app_localizations.dart';

class MedicationShell extends ConsumerStatefulWidget {
  const MedicationShell({super.key, required this.child});
  final Widget child;
  @override
  ConsumerState<MedicationShell> createState() => _MedicationShellState();
}

class _MedicationShellState extends ConsumerState<MedicationShell>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    Future.microtask(() {
      if (mounted &&
          ref.read(accountProvider).status == AccountStatus.initial) {
        ref.read(accountProvider).restore();
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) ref.read(accountProvider).restore();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final account = ref.watch(accountProvider);
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
          IconButton(
            key: const Key('account'),
            tooltip: s.account,
            onPressed: () => context.push('/account'),
            icon: const Icon(Icons.person_outline),
          ),
        ],
      ),
      body: SafeArea(
        child: account.status == AccountStatus.signedIn && !account.busy
            ? KeyedSubtree(key: ValueKey(account.userId), child: widget.child)
            : Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (account.busy) const CircularProgressIndicator(),
                      Text(
                        account.errorCode == 'session_expired'
                            ? s.sessionExpired
                            : s.onlineNotice,
                      ),
                      FilledButton(
                        onPressed: () => context.go('/account'),
                        child: Text(s.account),
                      ),
                    ],
                  ),
                ),
              ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            children: [
              TextButton(
                onPressed: () => context.go('/home'),
                child: Text(s.todayDoses),
              ),
              TextButton(
                onPressed: () => context.go('/medications'),
                child: Text(s.medications),
              ),
              TextButton(
                onPressed: () => context.go('/history'),
                child: Text(s.doseHistory),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ManualError extends StatelessWidget {
  const ManualError(this.code, {super.key});
  final String code;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final conflict =
        code.contains('conflict') ||
        code.contains('stale') ||
        code.startsWith('preview');
    return Semantics(
      liveRegion: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Text(
          code == 'save_uncertain'
              ? s.saveUncertain
              : conflict
              ? s.manualConflict
              : s.manualError,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      ),
    );
  }
}

String doseStatus(AppLocalizations s, String status) => switch (status) {
  'taken' => s.taken,
  'skipped' => s.skipped,
  'cancelled' => s.cancelled,
  'corrected' => s.corrected,
  _ => s.pending,
};

class ManualPage extends StatelessWidget {
  const ManualPage({super.key, required this.children});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => Center(
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 900),
      child: FocusTraversalGroup(
        child: ListView(padding: const EdgeInsets.all(24), children: children),
      ),
    ),
  );
}
