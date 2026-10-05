import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../l10n/app_localizations.dart';
import 'medication_providers.dart';
import 'medication_shell.dart';

class MedicationListScreen extends ConsumerStatefulWidget {
  const MedicationListScreen({super.key});
  @override
  ConsumerState<MedicationListScreen> createState() => _ListState();
}

class _ListState extends ConsumerState<MedicationListScreen> {
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
        Text(s.medications, style: Theme.of(context).textTheme.headlineMedium),
        Text(s.manualNotice),
        CheckboxListTile(
          value: state.includeRemoved,
          title: Text(s.includeRemoved),
          onChanged: state.busy
              ? null
              : (value) {
                  state.includeRemoved = value ?? false;
                  state.medications = [];
                  state.refresh();
                },
        ),
        FilledButton(
          onPressed: () => context.push('/medications/new'),
          child: Text(s.addMedication),
        ),
        OutlinedButton(
          onPressed: state.busy ? null : state.refresh,
          child: Text(s.refreshData),
        ),
        if (state.busy) const LinearProgressIndicator(),
        if (state.error != null) ManualError(state.error!),
        if (!state.busy && state.error == null && state.medications.isEmpty)
          Text(s.noMedications),
        for (final medication in state.medications)
          Card(
            child: TextButton(
              onPressed: () => context.push('/medications/${medication.id}'),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: SizedBox(
                  width: double.infinity,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        medication.displayName,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      Text(medication.doseText),
                      Text(
                        medication.deletedAt != null
                            ? s.removedRecord
                            : medication.schedule == null
                            ? s.savedNoSchedule
                            : s.scheduleActive,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
