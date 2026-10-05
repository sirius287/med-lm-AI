import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../l10n/app_localizations.dart';
import 'medication_providers.dart';
import 'medication_service.dart';
import 'medication_shell.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});
  @override
  ConsumerState<HistoryScreen> createState() => _HistoryState();
}

class _HistoryState extends ConsumerState<HistoryScreen> {
  final start = TextEditingController(), end = TextEditingController();
  final form = GlobalKey<FormState>();
  late DateTime appliedStart, appliedEnd;
  @override
  void initState() {
    super.initState();
    final today = ref.read(medicationControllerProvider).today;
    start.text = isoDate(today.subtract(const Duration(days: 7)));
    end.text = isoDate(today);
    appliedStart = DateTime(today.year, today.month, today.day - 7);
    appliedEnd = DateTime(today.year, today.month, today.day);
    Future.microtask(load);
  }

  Future<void> load() async {
    if (!mounted) return;
    final a = DateTime.tryParse(start.text), b = DateTime.tryParse(end.text);
    if (a != null &&
        b != null &&
        isoDate(a) == start.text &&
        isoDate(b) == end.text &&
        b.difference(a).inDays >= 0 &&
        b.difference(a).inDays < 90) {
      appliedStart = a;
      appliedEnd = b;
      await ref.read(medicationControllerProvider).loadHistory(a, b);
    }
  }

  @override
  void dispose() {
    start.dispose();
    end.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!,
        state = ref.watch(medicationControllerProvider);
    if (!state.historyInitialized && !state.busy) Future.microtask(load);
    String? validate(String? v) {
      final d = DateTime.tryParse(v ?? '');
      return d == null || isoDate(d) != v ? s.requiredField : null;
    }

    return ManualPage(
      children: [
        Text(s.doseHistory, style: Theme.of(context).textTheme.headlineMedium),
        Text(s.indiaDisplayZone),
        Form(
          key: form,
          child: Column(
            children: [
              TextFormField(
                controller: start,
                decoration: InputDecoration(labelText: s.startDate),
                validator: validate,
              ),
              TextFormField(
                controller: end,
                decoration: InputDecoration(labelText: s.endDate),
                validator: (v) {
                  final basic = validate(v);
                  final a = DateTime.tryParse(start.text),
                      b = DateTime.tryParse(v ?? '');
                  return basic ??
                      (a == null ||
                              b == null ||
                              b.difference(a).inDays < 0 ||
                              b.difference(a).inDays >= 90
                          ? s.requiredField
                          : null);
                },
              ),
              FilledButton(
                onPressed: state.busy
                    ? null
                    : () {
                        if (form.currentState!.validate()) load();
                      },
                child: Text(s.applyDates),
              ),
            ],
          ),
        ),
        if (state.busy) const LinearProgressIndicator(),
        if (state.error != null) ManualError(state.error!),
        if (!state.busy && state.error == null && state.history.isEmpty)
          Text(s.noHistory),
        for (final event in state.history)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(event.doseSnapshot['display_name'] as String),
                  Text(event.doseSnapshot['dose_text'] as String),
                  Text(
                    event.kind == 'corrected' &&
                            event.payload['corrected_status'] is String
                        ? '${s.corrected}: ${doseStatus(s, event.payload['corrected_status'] as String)}'
                        : doseStatus(s, event.kind),
                  ),
                  Text(event.originalLocalTime ?? ''),
                  Text(event.recordedAt),
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
                              await state.correctHistory(
                                event,
                                value,
                                appliedStart,
                                appliedEnd,
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
