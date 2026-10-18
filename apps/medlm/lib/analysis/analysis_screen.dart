import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import 'analysis_widgets.dart';
import 'synthetic_analysis_controller.dart';

class AnalysisScreen extends StatelessWidget {
  const AnalysisScreen(this.controller, {super.key});
  final SyntheticAnalysisController controller;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final a = controller.analysis;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AnalysisHeading(s.analysisObservations),
        if (a != null) ...[
          Text('${s.analysisProcessing}: ${analysisLabel(s, a.job.state)}'),
          Text(
            '${s.analysisAvailability}: ${analysisLabel(s, a.availability)}',
          ),
          Text('${s.analysisDeadline}: ${a.expiresAt}'),
          if (a.availability == 'expired' || controller.isExpired)
            Text(s.analysisExpiredNotice),
          if (a.availability == 'cancelled') Text(s.analysisCancelledNotice),
        ],
        if (controller.observations != null)
          ObservationList(controller.observations!),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            if (controller.observations != null)
              FilledButton(
                key: const Key('analysis-review'),
                onPressed:
                    !controller.busy &&
                        !controller.uncertain &&
                        (controller.canMutate || controller.review != null)
                    ? controller.beginReview
                    : null,
                child: Text(s.analysisReview),
              ),
            if (controller.report != null)
              OutlinedButton(
                key: const Key('analysis-report'),
                onPressed: controller.showReport,
                child: Text(s.analysisReport),
              ),
            if (controller.canNewAttempt)
              OutlinedButton(
                key: const Key('analysis-new-attempt'),
                onPressed: controller.newAttempt,
                child: Text(s.analysisNewAttempt),
              ),
          ],
        ),
      ],
    );
  }
}
