import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../app/providers.dart';
import '../core/api_client.dart';
import '../l10n/app_localizations.dart';
import 'generated/manual_models.dart';
import 'medication_providers.dart';
import 'medication_shell.dart';

class MedicationDetailScreen extends ConsumerStatefulWidget {
  const MedicationDetailScreen({super.key, required this.id});
  final String id;
  @override
  ConsumerState<MedicationDetailScreen> createState() => _DetailState();
}

class _DetailState extends ConsumerState<MedicationDetailScreen> {
  MedicationView? medication;
  String? error;
  bool busy = true;
  @override
  void initState() {
    super.initState();
    Future.microtask(load);
  }

  Future<void> load() async {
    if (!mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final value = await ref.read(medicationServiceProvider).get(widget.id);
      if (mounted) setState(() => medication = value);
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => error = e.code);
        if (e.status == 401) ref.read(accountProvider).expire();
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final m = medication;
    return ManualPage(
      children: [
        if (busy) const LinearProgressIndicator(),
        if (error != null) ManualError(error!),
        OutlinedButton(
          onPressed: busy ? null : load,
          child: Text(s.refreshData),
        ),
        if (m != null) ...[
          Text(
            m.displayName,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          Text(s.manualNotice),
          if (m.strengthText != null)
            Text('${s.strengthText}: ${m.strengthText}'),
          Text('${s.doseText}: ${m.doseText}'),
          if (m.routeText != null) Text('${s.routeText}: ${m.routeText}'),
          if (m.instructions != null) Text(m.instructions!),
          Text(m.schedule == null ? s.savedNoSchedule : s.scheduleActive),
          if (m.schedule != null)
            Text(
              '${m.schedule!['time_zone']} · ${m.schedule!['start_date']} → ${m.schedule!['end_date'] ?? s.openEnded}',
            ),
          if (m.deletedAt == null)
            FilledButton(
              onPressed: busy
                  ? null
                  : () => context.push('/medications/${m.id}/edit').then((_) {
                      if (mounted) load();
                    }),
              child: Text(s.editMedication),
            ),
          OutlinedButton(
            onPressed: () => context.go('/history'),
            child: Text(s.viewHistory),
          ),
          OutlinedButton(
            onPressed: busy
                ? null
                : () async {
                    bool erase = false;
                    final confirmed = await showDialog<bool>(
                      context: context,
                      builder: (context) => StatefulBuilder(
                        builder: (context, update) => AlertDialog(
                          title: Text(s.removeMedication),
                          content: SingleChildScrollView(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(s.removeNotice),
                                CheckboxListTile(
                                  value: erase,
                                  onChanged: (v) =>
                                      update(() => erase = v ?? false),
                                  title: Text(s.eraseHistory),
                                ),
                              ],
                            ),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(context, false),
                              child: Text(s.cancelAction),
                            ),
                            FilledButton(
                              onPressed: () => Navigator.pop(context, true),
                              child: Text(s.confirmAction),
                            ),
                          ],
                        ),
                      ),
                    );
                    if (confirmed != true || !mounted) return;
                    setState(() => busy = true);
                    try {
                      await ref
                          .read(medicationServiceProvider)
                          .remove(m, erase: erase);
                      if (context.mounted) context.go('/medications');
                    } on ApiException catch (e) {
                      if (mounted) {
                        setState(() => error = e.code);
                        if (e.status == 401) ref.read(accountProvider).expire();
                      }
                    } finally {
                      if (mounted) setState(() => busy = false);
                    }
                  },
            child: Text(s.removeMedication),
          ),
        ],
      ],
    );
  }
}
