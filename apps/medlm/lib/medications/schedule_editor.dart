import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../l10n/app_localizations.dart';
import 'medication_service.dart';

class ScheduleFields {
  String kind = 'daily_times';
  bool openEnded = false;
  final days = <int>{};
  final zone = TextEditingController(text: 'Asia/Kolkata');
  final start = TextEditingController(),
      end = TextEditingController(),
      times = TextEditingController(),
      interval = TextEditingController(),
      anchor = TextEditingController();
  void load(Map<String, dynamic>? data) {
    if (data == null) return;
    kind = data['kind'] as String;
    openEnded = data['open_ended'] as bool;
    zone.text = data['time_zone'] as String;
    start.text = data['start_date'] as String;
    end.text = data['end_date'] as String? ?? '';
    times.text = (data['local_times'] as List)
        .map((e) => (e as String).substring(0, 5))
        .join(', ');
    days.clear();
    days.addAll((data['weekdays'] as List).cast<int>());
    interval.text = data['interval_hours']?.toString() ?? '';
    anchor.text = (data['anchor_at'] ?? data['one_time_at']) as String? ?? '';
  }

  Map<String, dynamic> body() => {
    'kind': kind,
    'time_zone': zone.text.trim(),
    'start_date': start.text.trim(),
    'end_date': openEnded ? null : end.text.trim(),
    'open_ended': openEnded,
    if (kind == 'daily_times' || kind == 'weekdays')
      'local_times': times.text.split(',').map((s) => s.trim()).toList(),
    if (kind == 'weekdays') 'weekdays': days.toList()..sort(),
    if (kind == 'fixed_interval') 'interval_hours': interval.text.trim(),
    if (kind == 'fixed_interval') 'anchor_at': anchor.text.trim(),
    if (kind == 'one_time') 'one_time_at': anchor.text.trim(),
  };
  void dispose() {
    for (final c in [zone, start, end, times, interval, anchor]) {
      c.dispose();
    }
  }
}

class ScheduleEditor extends StatelessWidget {
  const ScheduleEditor({
    super.key,
    required this.fields,
    required this.onChanged,
    required this.enabled,
  });
  final ScheduleFields fields;
  final VoidCallback onChanged;
  final bool enabled;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final f = fields;
    String? required(String? value) =>
        value == null || value.trim().isEmpty ? s.requiredField : null;
    Widget text(
      TextEditingController c,
      String label, {
      String? Function(String?)? validator,
    }) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: TextFormField(
        controller: c,
        enabled: enabled,
        decoration: InputDecoration(labelText: label),
        validator: validator ?? required,
        onChanged: (_) => onChanged(),
      ),
    );
    Widget dateField(TextEditingController c, String label) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: TextFormField(
        controller: c,
        enabled: enabled,
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: IconButton(
            tooltip: label,
            onPressed: !enabled
                ? null
                : () async {
                    final date = await showDatePicker(
                      context: context,
                      firstDate: DateTime(2020),
                      lastDate: DateTime(2100),
                      initialDate: DateTime.tryParse(c.text) ?? DateTime.now(),
                    );
                    if (date != null) {
                      c.text = isoDate(date);
                      onChanged();
                    }
                  },
            icon: const Icon(Icons.calendar_today_outlined),
          ),
        ),
        validator: (v) {
          final value = DateTime.tryParse(v ?? '');
          if (value == null || isoDate(value) != v) return s.requiredField;
          if (c == f.end) {
            final start = DateTime.tryParse(f.start.text);
            if (start != null && value.isBefore(start)) return s.requiredField;
          }
          return null;
        },
        onChanged: (_) => onChanged(),
      ),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(s.scheduleLabel, style: Theme.of(context).textTheme.titleLarge),
        DropdownButtonFormField<String>(
          itemHeight: null,
          initialValue: f.kind,
          isExpanded: true,
          decoration: InputDecoration(labelText: s.scheduleLabel),
          items: [
            DropdownMenuItem(value: 'daily_times', child: Text(s.dailyTimes)),
            DropdownMenuItem(
              value: 'weekdays',
              child: Text(s.selectedWeekdays),
            ),
            DropdownMenuItem(
              value: 'fixed_interval',
              child: Text(s.fixedInterval),
            ),
            DropdownMenuItem(value: 'one_time', child: Text(s.oneTime)),
          ],
          onChanged: !enabled
              ? null
              : (value) {
                  if (value != null) {
                    f.kind = value;
                    onChanged();
                  }
                },
        ),
        text(f.zone, s.timeZone),
        dateField(f.start, s.startDate),
        CheckboxListTile(
          value: f.openEnded,
          onChanged: !enabled
              ? null
              : (v) {
                  f.openEnded = v ?? false;
                  onChanged();
                },
          title: Text(s.openEnded),
          controlAffinity: ListTileControlAffinity.leading,
        ),
        if (!f.openEnded) dateField(f.end, s.endDate),
        if (f.kind == 'daily_times' || f.kind == 'weekdays')
          text(
            f.times,
            s.clockTimes,
            validator: (v) {
              final parts = (v ?? '').split(',').map((e) => e.trim()).toList();
              return parts.isEmpty ||
                      parts.length > 12 ||
                      parts.toSet().length != parts.length ||
                      parts.any(
                        (e) =>
                            !RegExp(r'^([01]\d|2[0-3]):[0-5]\d$').hasMatch(e),
                      )
                  ? s.requiredField
                  : null;
            },
          ),
        if (f.kind == 'weekdays')
          FormField<bool>(
            validator: (_) => f.days.isEmpty ? s.requiredField : null,
            builder: (field) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  children: [
                    for (var day = 0; day < 7; day++)
                      FilterChip(
                        label: Text(
                          DateFormat.E(
                            Localizations.localeOf(context).toString(),
                          ).format(DateTime(2024, 1, 1 + day)),
                        ),
                        selected: f.days.contains(day),
                        onSelected: !enabled
                            ? null
                            : (selected) {
                                selected ? f.days.add(day) : f.days.remove(day);
                                onChanged();
                              },
                      ),
                  ],
                ),
                if (field.hasError)
                  Text(
                    field.errorText!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
              ],
            ),
          ),
        if (f.kind == 'fixed_interval')
          text(
            f.interval,
            s.intervalHours,
            validator: (v) {
              final n = num.tryParse(v ?? '');
              return n == null || n < 1 || n > 8760 ? s.requiredField : null;
            },
          ),
        if (f.kind == 'fixed_interval' || f.kind == 'one_time')
          text(
            f.anchor,
            s.anchorInstant,
            validator: (v) =>
                DateTime.tryParse(v ?? '') == null ||
                    !RegExp(r'(Z|[+-]\d\d:\d\d)$').hasMatch(v ?? '')
                ? s.requiredField
                : null,
          ),
        Text(s.dstNotice),
      ],
    );
  }
}
