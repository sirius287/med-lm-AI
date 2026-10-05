import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../app/providers.dart';
import '../core/api_client.dart';
import '../l10n/app_localizations.dart';
import 'generated/manual_models.dart';
import 'medication_providers.dart';
import 'medication_service.dart';
import 'medication_shell.dart';
import 'schedule_editor.dart';

class MedicationFormScreen extends ConsumerStatefulWidget {
  const MedicationFormScreen({super.key, this.id});
  final String? id;
  @override
  ConsumerState<MedicationFormScreen> createState() => _FormState();
}

class _FormState extends ConsumerState<MedicationFormScreen> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController(),
      strength = TextEditingController(),
      dose = TextEditingController(),
      route = TextEditingController(),
      instructions = TextEditingController();
  final schedule = ScheduleFields();
  MedicationView? saved;
  PreviewView? preview;
  String? error, savedFields;
  String createKey = requestId(),
      previewKey = requestId(),
      activationKey = requestId();
  bool busy = false, uncertain = false, instructionsSaved = false;
  Map<String, dynamic>? uncertainFields;
  @override
  void initState() {
    super.initState();
    if (widget.id != null) Future.microtask(load);
  }

  Future<void> load() async {
    if (!mounted) return;
    setState(() => busy = true);
    try {
      final m = await ref
          .read(medicationServiceProvider)
          .get(widget.id ?? saved!.id);
      if (!mounted) return;
      saved = m;
      name.text = m.displayName;
      strength.text = m.strengthText ?? '';
      dose.text = m.doseText;
      route.text = m.routeText ?? '';
      instructions.text = m.instructions ?? '';
      schedule.load(m.schedule);
      savedFields = jsonEncode(fields());
      uncertain = false;
      uncertainFields = null;
      instructionsSaved = false;
      error = null;
      preview = null;
    } on ApiException catch (e) {
      handle(e);
    } catch (_) {
      if (mounted) setState(() => error = 'invalid_response');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void handle(ApiException e) {
    if (!mounted) return;
    setState(() => error = e.code);
    if (e.status == 401) ref.read(accountProvider).expire();
  }

  Map<String, dynamic> fields() => {
    'display_name': name.text.trim(),
    'strength_text': strength.text.trim().isEmpty ? null : strength.text.trim(),
    'dose_text': dose.text.trim(),
    'route_text': route.text.trim().isEmpty ? null : route.text.trim(),
    'instructions': instructions.text.trim().isEmpty
        ? null
        : instructions.text.trim(),
  };
  void changed() {
    setState(() {
      preview = null;
      previewKey = requestId();
      activationKey = requestId();
      if (saved == null && !uncertain) createKey = requestId();
    });
  }

  Future<void> save() async {
    if (busy || !form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    final service = ref.read(medicationServiceProvider);
    try {
      final input = uncertainFields ?? fields();
      if (saved == null || savedFields != jsonEncode(input)) {
        try {
          final record = await service.save(input, createKey, existing: saved);
          if (!mounted) return;
          saved = record;
          instructionsSaved = true;
          savedFields = jsonEncode(input);
          uncertain = false;
          uncertainFields = null;
        } on ApiException catch (e) {
          if (e.status == null || e.status! >= 500) {
            uncertain = true;
            uncertainFields = input;
          }
          rethrow;
        }
      }
      final result = await service.preview(
        saved!.id,
        schedule.body(),
        previewKey,
      );
      if (result.medicationVersion != saved!.version) {
        throw const ApiException('stale_version', status: 412);
      }
      if (mounted) setState(() => preview = result);
    } on ApiException catch (e) {
      handle(e);
      if (mounted && uncertain) setState(() => error = 'save_uncertain');
    } catch (_) {
      if (mounted) setState(() => error = 'invalid_response');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> activateSchedule() async {
    if (preview == null || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final m = await ref
          .read(medicationServiceProvider)
          .activate(saved!.id, schedule.body(), preview!, activationKey);
      if (mounted) context.go('/medications/${m.id}');
    } on ApiException catch (e) {
      handle(e);
      if (mounted && (e.status == 409 || e.status == 412)) {
        setState(() {
          preview = null;
          previewKey = requestId();
          activationKey = requestId();
        });
      }
    } catch (_) {
      if (mounted) setState(() => error = 'invalid_response');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    for (final c in [name, strength, dose, route, instructions]) {
      c.dispose();
    }
    schedule.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    Widget field(
      TextEditingController c,
      String label,
      int max, {
      bool required = false,
      int lines = 1,
    }) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: TextFormField(
        controller: c,
        enabled: !busy && !uncertain,
        maxLength: max,
        minLines: lines,
        maxLines: lines,
        decoration: InputDecoration(labelText: label),
        validator: (v) => required && (v == null || v.trim().isEmpty)
            ? s.requiredField
            : null,
        onChanged: (_) => changed(),
      ),
    );
    return ManualPage(
      children: [
        Text(
          widget.id == null ? s.addMedication : s.editMedication,
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        Text(s.manualNotice),
        Text(s.onlineNotice),
        if (busy) const LinearProgressIndicator(),
        if (error != null) ManualError(error!),
        if (instructionsSaved && preview == null)
          Semantics(liveRegion: true, child: Text(s.savedNoSchedule)),
        if (widget.id != null || saved != null)
          OutlinedButton(
            onPressed: busy ? null : load,
            child: Text(s.refreshData),
          ),
        Form(
          key: form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              field(name, s.medicineName, 200, required: true),
              field(strength, s.strengthText, 200),
              field(dose, s.doseText, 500, required: true, lines: 2),
              field(route, s.routeText, 200),
              field(instructions, s.additionalInstructions, 2000, lines: 3),
              ScheduleEditor(
                fields: schedule,
                onChanged: changed,
                enabled: !busy && !uncertain,
              ),
              FilledButton(
                onPressed:
                    busy ||
                        (uncertain && saved != null) ||
                        (widget.id != null && saved == null)
                    ? null
                    : save,
                child: Text(s.saveAndPreview),
              ),
            ],
          ),
        ),
        if (preview != null) ...[
          Semantics(
            header: true,
            child: Text(
              s.schedulePreview,
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ),
          Text(s.dstNotice),
          for (final occurrence in preview!.occurrences)
            Text(occurrence['original_local_time'] as String),
          FilledButton(
            onPressed: busy ? null : activateSchedule,
            child: Text(s.activateSchedule),
          ),
        ],
      ],
    );
  }
}
