import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/providers.dart';
import '../auth/auth_controller.dart';
import '../l10n/app_localizations.dart';
import 'analysis_report_screen.dart';
import 'analysis_review_screen.dart';
import 'analysis_screen.dart';
import 'analysis_widgets.dart';
import 'fixture_selection_screen.dart';
import 'synthetic_analysis_controller.dart';
import 'synthetic_analysis_providers.dart';
import 'synthetic_analysis_service.dart';

/// Explicitly mounted by tests only. No main entry, normal route, auth override,
/// environment enable flag, local server bootstrap or default service instance.
class SyntheticAnalysisHarness extends StatelessWidget {
  const SyntheticAnalysisHarness({super.key, required this.service});
  final SyntheticAnalysisService service;
  @override
  Widget build(BuildContext context) => ProviderScope(
    overrides: [syntheticAnalysisServiceProvider.overrideWithValue(service)],
    child: const _Workspace(),
  );
}

class _Workspace extends ConsumerStatefulWidget {
  const _Workspace();
  @override
  ConsumerState<_Workspace> createState() => _WorkspaceState();
}

class _WorkspaceState extends ConsumerState<_Workspace>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
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
    // Keep the owner-scoped controller observed while the locked UI revalidates.
    // Its provider clears state on failed authentication/logout/owner changes.
    final c = ref.watch(syntheticAnalysisControllerProvider);
    if (account.status != AccountStatus.signedIn ||
        account.userId == null ||
        account.busy) {
      return Scaffold(
        appBar: AppBar(title: Text(s.analysisTitle)),
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (account.busy) const CircularProgressIndicator(),
                  Text(
                    account.errorCode == 'session_expired'
                        ? s.sessionExpired
                        : s.sessionUnavailable,
                  ),
                  FilledButton(
                    onPressed: account.busy ? null : account.restore,
                    child: Text(s.retry),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }
    final error = c.error;
    final errorText = error == null
        ? null
        : analysisErrorLabel(s, error, c.needsRefresh);
    return Scaffold(
      appBar: AppBar(title: Text(s.analysisTitle)),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1000),
            child: FocusTraversalGroup(
              child: ListView(
                key: ValueKey('synthetic-owner-${account.userId}-${c.page}'),
                padding: const EdgeInsets.all(24),
                children: [
                  Text(s.analysisSyntheticNotice),
                  const SizedBox(height: 16),
                  if (c.busy) ...[
                    const LinearProgressIndicator(),
                    Semantics(liveRegion: true, child: Text(s.analysisLoading)),
                  ],
                  if (error != null && c.page != SyntheticPage.review)
                    Semantics(
                      liveRegion: true,
                      child: Text(
                        errorText!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  if (c.uncertain && c.page != SyntheticPage.review) ...[
                    Text(s.analysisUncertain),
                    FilledButton(
                      key: const Key('analysis-replay'),
                      onPressed: c.busy ? null : c.retryPending,
                      child: Text(s.analysisRetrySame),
                    ),
                  ],
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      if (c.analysis != null)
                        OutlinedButton(
                          key: const Key('analysis-refresh'),
                          onPressed: c.busy ? null : c.refresh,
                          child: Text(s.refreshData),
                        ),
                      if (c.canMutate)
                        OutlinedButton(
                          key: const Key('analysis-cancel'),
                          onPressed: c.cancel,
                          child: Text(s.analysisCancel),
                        ),
                      if (c.page != SyntheticPage.fixtures &&
                          c.page != SyntheticPage.observations)
                        TextButton(
                          onPressed: c.showObservations,
                          child: Text(s.analysisBack),
                        ),
                      if (c.page != SyntheticPage.fixtures &&
                          !c.canMutate &&
                          !c.busy &&
                          !c.uncertain)
                        OutlinedButton(
                          onPressed: c.reset,
                          child: Text(s.analysisNewFixture),
                        ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  switch (c.page) {
                    SyntheticPage.fixtures => FixtureSelectionScreen(c),
                    SyntheticPage.observations => AnalysisScreen(c),
                    SyntheticPage.review => AnalysisReviewScreen(c),
                    SyntheticPage.report =>
                      c.report == null
                          ? Text(s.analysisConflict)
                          : AnalysisReportScreen(c.report!),
                  },
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
