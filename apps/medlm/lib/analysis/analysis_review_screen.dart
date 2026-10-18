import 'package:flutter/material.dart';
import '../design_system/theme.dart';
import '../l10n/app_localizations.dart';
import 'analysis_validation.dart';
import 'analysis_widgets.dart';
import 'generated/analysis_models.dart';
import 'synthetic_analysis_controller.dart';

class AnalysisReviewScreen extends StatelessWidget {
  const AnalysisReviewScreen(this.controller, {super.key});
  final SyntheticAnalysisController controller;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final review = controller.review;
    if (review == null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AnalysisHeading(s.analysisReview),
          Semantics(
            key: const Key('review-recovery-error'),
            liveRegion: true,
            child: Text(
              controller.error == null
                  ? s.analysisConflict
                  : analysisErrorLabel(
                      s,
                      controller.error!,
                      controller.needsRefresh,
                    ),
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
          if (controller.uncertain) ...[
            Text(s.analysisUncertain),
            OutlinedButton(
              key: const Key('review-replay'),
              onPressed: controller.busy ? null : controller.retryPending,
              child: Text(s.analysisRetrySame),
            ),
          ],
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              OutlinedButton(
                key: const Key('review-reload'),
                onPressed: controller.busy || controller.analysis == null
                    ? null
                    : controller.refresh,
                child: Text(s.refreshData),
              ),
              TextButton(
                key: const Key('review-overview'),
                onPressed: controller.showObservations,
                child: Text(s.analysisBack),
              ),
            ],
          ),
        ],
      );
    }
    final fields = observedFields(review.extraction);
    final lines = [...review.extraction.lines]
      ..sort((a, b) => a.ordinal.compareTo(b.ordinal));
    Widget editor(String key) => ReviewFieldEditor(
      key: ValueKey('${review.revision}:${review.version}:$key'),
      fieldKey: key,
      observation: fields[key]!,
      controller: controller,
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AnalysisHeading(s.analysisReview),
        Text(s.analysisUnverified),
        if (review.closed) Text(s.analysisFinalNotice),
        if (!review.imageAvailable) Text(s.analysisImageUnavailable),
        if (lines.isEmpty) ...[
          for (final key in review.requiredFieldKeys) editor(key),
        ] else ...[
          for (final line in lines) ...[
            AnalysisHeading('${s.analysisLine} ${line.ordinal + 1}'),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: DropdownButtonFormField<String>(
                key: ValueKey('disposition-${line.lineId}-${review.version}'),
                initialValue: controller.dispositions[line.lineId],
                isExpanded: true,
                decoration: InputDecoration(
                  labelText: s.analysisDisposition,
                  helperText: s.analysisSelectDisposition,
                  helperMaxLines: 4,
                ),
                items: [
                  for (final value in ['included', 'excluded', 'unresolved'])
                    DropdownMenuItem(
                      value: value,
                      child: Text(analysisLabel(s, value)),
                    ),
                ],
                onChanged: controller.canEditReview
                    ? (value) {
                        if (value != null) {
                          controller.disposition(line.lineId, value);
                        }
                      }
                    : null,
              ),
            ),
            for (final key in prescriptionObservationKeys)
              editor('${line.lineId}.$key'),
          ],
        ],
        if (controller.error != null)
          Semantics(
            liveRegion: true,
            child: Text(
              analysisErrorLabel(s, controller.error!, controller.needsRefresh),
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        if (controller.uncertain) ...[
          Text(s.analysisUncertain),
          OutlinedButton(
            key: const Key('review-replay'),
            onPressed: controller.busy ? null : controller.retryPending,
            child: Text(s.analysisRetrySame),
          ),
        ],
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            for (final (decision, label) in [
              ('confirm', s.analysisConfirmText),
              ('correct', s.analysisCorrectText),
              ('reject', s.analysisReject),
              ('unresolved', s.analysisSaveUnresolved),
            ])
              FilledButton(
                key: ValueKey('review-submit-$decision'),
                onPressed: controller.canEditReview
                    ? () => controller.submitReview(decision)
                    : null,
                child: Text(label),
              ),
          ],
        ),
      ],
    );
  }
}

class ReviewFieldEditor extends StatefulWidget {
  const ReviewFieldEditor({
    super.key,
    required this.fieldKey,
    required this.observation,
    required this.controller,
  });
  final String fieldKey;
  final ExtractionField observation;
  final SyntheticAnalysisController controller;
  @override
  State<ReviewFieldEditor> createState() => _ReviewFieldState();
}

class _ReviewFieldState extends State<ReviewFieldEditor> {
  late final TextEditingController correction;
  bool clear = false;
  @override
  void initState() {
    super.initState();
    final prior = widget.controller.fields[widget.fieldKey]!;
    correction = TextEditingController(
      text: prior.status == 'corrected' ? prior.reviewedValue ?? '' : '',
    );
    clear = prior.status == 'corrected' && prior.reviewedValue == null;
  }

  @override
  void dispose() {
    correction.clear();
    correction.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final c = widget.controller, key = widget.fieldKey;
    final status = c.fields[key]?.status ?? 'unreviewed';
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: SoftPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              header: true,
              child: Text(
                analysisLabel(s, key.split('.').last),
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Text(
              '${s.analysisOriginal}: ${widget.observation.rawText ?? s.analysisNoObservedText}',
            ),
            if (widget.observation.ambiguityReason != null) ...[
              Text(s.analysisAlternatives),
              Text(widget.observation.ambiguityReason!),
              for (final text in widget.observation.alternatives) Text(text),
            ],
            Semantics(liveRegion: true, child: Text(analysisLabel(s, status))),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                OutlinedButton(
                  key: ValueKey('confirm-$key'),
                  onPressed: c.canEditReview
                      ? () {
                          correction.clear();
                          setState(() => clear = false);
                          c.confirmField(key);
                        }
                      : null,
                  child: Text(s.analysisConfirmField),
                ),
                TextButton(
                  onPressed: c.canEditReview
                      ? () => c.unresolvedField(key)
                      : null,
                  child: Text(s.analysisUnresolved),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              key: ValueKey('correction-$key'),
              controller: correction,
              enabled: c.canEditReview && !clear,
              maxLength: 2000,
              minLines: 1,
              maxLines: 3,
              decoration: InputDecoration(labelText: s.analysisCorrection),
              onChanged: (value) => c.correctField(key, value),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(s.analysisClearValue),
              value: clear,
              onChanged: c.canEditReview
                  ? (value) {
                      setState(() => clear = value!);
                      c.correctField(key, clear ? null : correction.text);
                    }
                  : null,
            ),
          ],
        ),
      ),
    );
  }
}
