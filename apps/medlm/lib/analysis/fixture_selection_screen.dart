import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import 'analysis_widgets.dart';
import 'generated/synthetic_fixture_catalog.dart';
import 'synthetic_analysis_controller.dart';

class FixtureSelectionScreen extends StatelessWidget {
  const FixtureSelectionScreen(this.controller, {super.key});
  final SyntheticAnalysisController controller;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AnalysisHeading(s.analysisChooseFixture),
        for (final fixture in bundledFixtures)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: OutlinedButton(
              key: ValueKey('fixture-${fixture.id}'),
              onPressed: controller.busy
                  ? null
                  : () => controller.start(
                      fixture,
                      '${s.localeName.split('_').first}-IN',
                    ),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  '${analysisLabel(s, fixture.kind)} · ${fixture.id.contains('_empty')
                      ? s.analysisFixtureEmpty
                      : fixture.id.contains('_ambiguous')
                      ? s.analysisFixtureAmbiguous
                      : s.analysisFixtureLiteral}',
                ),
              ),
            ),
          ),
      ],
    );
  }
}
