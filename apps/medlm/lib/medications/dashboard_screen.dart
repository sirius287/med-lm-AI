import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../l10n/app_localizations.dart';
import 'medication_providers.dart';
import 'medication_shell.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});
  @override
  ConsumerState<DashboardScreen> createState() => _DashboardState();
}

class _DashboardState extends ConsumerState<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (mounted) ref.read(medicationControllerProvider).refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final state = ref.watch(medicationControllerProvider);
    if (!state.initialized && !state.busy) Future.microtask(state.refresh);
    return ManualPage(
      children: [
        Semantics(
          header: true,
          child: Text(
            s.todayDoses,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
        ),
        Text(s.onlineNotice),
        Text(s.indiaDisplayZone),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          children: [
            FilledButton.icon(
              onPressed: () => context.push('/medications/new'),
              icon: const Icon(Icons.add),
              label: Text(s.addMedication),
            ),
            OutlinedButton(
              onPressed: state.busy ? null : state.refresh,
              child: Text(s.refreshData),
            ),
          ],
        ),
        if (state.busy) const LinearProgressIndicator(),
        if (state.error != null) ManualError(state.error!),
        if (!state.busy && state.doses.isEmpty && state.error == null)
          Text(s.noDoses),
        for (final dose in state.doses)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    dose.doseSnapshot['display_name'] as String,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  Text(dose.doseSnapshot['dose_text'] as String),
                  Text(dose.originalLocalTime ?? dose.plannedAt),
                  Semantics(
                    liveRegion: true,
                    child: Text(doseStatus(s, dose.status)),
                  ),
                  if (dose.actionable && dose.status == 'pending')
                    Wrap(
                      spacing: 12,
                      children: [
                        FilledButton(
                          onPressed: state.busy
                              ? null
                              : () => state.record(dose, 'taken'),
                          child: Text(s.taken),
                        ),
                        OutlinedButton(
                          onPressed: state.busy
                              ? null
                              : () => state.record(dose, 'skipped'),
                          child: Text(s.skipped),
                        ),
                      ],
                    ),
                  if (dose.actionable && dose.latestEventId != null)
                    OutlinedButton(
                      onPressed: state.busy
                          ? null
                          : () async {
                              final value = await showDialog<String>(
                                context: context,
                                builder: (context) => SimpleDialog(
                                  title: Text(s.correctDose),
                                  children: [
                                    for (final status in [
                                      'taken',
                                      'skipped',
                                      'pending',
                                    ])
                                      SimpleDialogOption(
                                        onPressed: () =>
                                            Navigator.pop(context, status),
                                        child: Padding(
                                          padding: const EdgeInsets.all(12),
                                          child: Text(doseStatus(s, status)),
                                        ),
                                      ),
                                  ],
                                ),
                              );
                              if (value != null && mounted) {
                                await state.record(
                                  dose,
                                  'corrected',
                                  correction: value,
                                );
                              }
                            },
                      child: Text(s.correctDose),
                    ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
