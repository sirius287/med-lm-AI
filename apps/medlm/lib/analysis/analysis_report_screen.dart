import 'package:flutter/material.dart';
import '../design_system/theme.dart';
import '../l10n/app_localizations.dart';
import 'analysis_widgets.dart';
import 'generated/analysis_models.dart';

class AnalysisReportScreen extends StatelessWidget {
  const AnalysisReportScreen(this.report, {super.key});
  final AnalysisReport report;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    String label(String key) {
      final parts = key.split('.');
      if (parts.length == 1) return analysisLabel(s, key);
      final line = report.observations.lines.firstWhere(
        (line) => line.lineId == parts.first,
      );
      return '${s.analysisLine} ${line.ordinal + 1} · ${analysisLabel(s, parts.last)}';
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AnalysisHeading(s.analysisReport),
        Text(s.analysisSyntheticNotice),
        Text(s.analysisUnverified),
        if (report.expired) Text(s.analysisExpiredNotice),
        if (report.cancelled) Text(s.analysisCancelledNotice),
        if (!report.imageAvailable) Text(s.analysisImageUnavailable),
        AnalysisHeading(s.analysisObservations),
        ObservationList(report.observations),
        AnalysisHeading(s.analysisReviewedText),
        Text(analysisLabel(s, report.reviewState)),
        Text(s.analysisSavedText),
        for (final entry in report.acceptedTranscription.entries)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(
              '${label(entry.key)}: ${entry.value ?? s.analysisNoObservedText}',
              key: ValueKey('reviewed-${entry.key}'),
            ),
          ),
        AnalysisHeading(s.analysisHistory),
        for (final item in report.reviewHistory)
          SoftPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(analysisLabel(s, item.review.decision)),
                for (final entry in item.review.lineDispositions.entries)
                  Text(
                    '${s.analysisLine} ${report.observations.lines.firstWhere((line) => line.lineId == entry.key).ordinal + 1}: ${analysisLabel(s, entry.value)}',
                  ),
                for (final entry in item.review.fields.entries)
                  Text(
                    '${label(entry.key)} · ${analysisLabel(s, entry.value.status)}: ${entry.value.reviewedValue ?? s.analysisNoObservedText}',
                  ),
              ],
            ),
          ),
        for (final key in medicalInformationKeys)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: SoftPanel(
              key: ValueKey('report-field-$key'),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Semantics(
                    header: true,
                    child: Text(
                      analysisLabel(s, key),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  Text(s.analysisUnavailableInfo),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
