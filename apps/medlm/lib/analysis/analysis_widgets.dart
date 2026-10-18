import 'package:flutter/material.dart';
import '../design_system/theme.dart';
import '../l10n/app_localizations.dart';
import 'generated/analysis_models.dart';

String analysisErrorLabel(AppLocalizations s, String code, bool stale) =>
    code == 'invalid_review'
    ? s.analysisInvalidReview
    : code == 'analysis_expired'
    ? s.analysisExpiredNotice
    : code == 'provider_disabled'
    ? s.analysisProviderDisabled
    : ['connection_failed', 'invalid_response', 'request_failed'].contains(code)
    ? s.analysisError
    : stale
    ? s.analysisConflict
    : s.analysisError;

String analysisLabel(AppLocalizations s, String key) => switch (key) {
  'medicine' || 'medicine_name' => s.medicineName,
  'generic_name' => s.analysisGenericName,
  'ingredients' || 'active_ingredients' => s.analysisActiveIngredients,
  'strength' => s.analysisStrength,
  'dosage_form' => s.analysisDosageForm,
  'manufacturer' => s.analysisManufacturer,
  'dose' => s.analysisDose,
  'frequency' => s.analysisFrequency,
  'route' => s.analysisRoute,
  'duration' => s.analysisDuration,
  'time' => s.analysisTime,
  'food_instruction' => s.analysisFoodInstruction,
  'special_instruction' => s.analysisSpecialInstruction,
  'common_uses' => s.analysisCommonUses,
  'mechanism_action' => s.analysisMechanism,
  'common_side_effects' => s.analysisCommonSideEffects,
  'serious_adverse_effects' => s.analysisSeriousEffects,
  'warnings' => s.analysisWarnings,
  'contraindications' => s.analysisContraindications,
  'precautions' => s.analysisPrecautions,
  'drug_interactions' => s.analysisDrugInteractions,
  'food_beverage_interactions' => s.analysisFoodInteractions,
  'pregnancy' => s.analysisPregnancy,
  'breastfeeding' => s.analysisBreastfeeding,
  'pediatric' => s.analysisPediatric,
  'older_adult' => s.analysisOlderAdult,
  'kidney' => s.analysisKidney,
  'liver' => s.analysisLiver,
  'storage' => s.analysisStorage,
  'prescription_otc_status' => s.analysisPrescriptionStatus,
  'other_information' => s.analysisOther,
  'strip' => s.analysisStrip,
  'bottle' => s.analysisBottle,
  'tube' => s.analysisTube,
  'box' => s.analysisBox,
  'prescription' => s.analysisPrescription,
  'queued' => s.analysisQueued,
  'validating' => s.analysisValidating,
  'extracting' => s.analysisExtracting,
  'retrieving' => s.analysisRetrieving,
  'validating_output' => s.analysisValidatingOutput,
  'completed' => s.analysisCompleted,
  'failed' => s.analysisFailed,
  'needs_input' => s.analysisNeedsInput,
  'cancelled' => s.cancelled,
  'available' => s.analysisAvailable,
  'expired' => s.analysisExpired,
  'unavailable' => s.analysisImageUnavailable,
  'unreviewed' => s.analysisUnreviewed,
  'confirmed' || 'confirm' => s.analysisConfirmed,
  'corrected' || 'correct' => s.analysisCorrected,
  'reject' => s.analysisReject,
  'unresolved' => s.analysisUnresolved,
  'included' => s.analysisIncluded,
  'excluded' => s.analysisExcluded,
  _ => s.analysisError,
};

class AnalysisHeading extends StatelessWidget {
  const AnalysisHeading(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Semantics(
      header: true,
      child: Text(text, style: Theme.of(context).textTheme.titleLarge),
    ),
  );
}

class ObservationTile extends StatelessWidget {
  const ObservationTile({
    super.key,
    required this.label,
    required this.observation,
  });
  final String label;
  final ExtractionField observation;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: SoftPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              header: true,
              child: Text(
                label,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Text(s.analysisOriginal),
            Text(observation.rawText ?? s.analysisNoObservedText),
            if (observation.normalizedValue != null) ...[
              Text(s.analysisNormalized),
              Text(observation.normalizedValue!),
            ],
            if (observation.ambiguityReason != null) ...[
              Text(
                s.analysisAlternatives,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
              Text(observation.ambiguityReason!),
              for (final value in observation.alternatives) Text(value),
            ],
            if (observation.confidence != null) Text(s.analysisUncalibrated),
          ],
        ),
      ),
    );
  }
}

class ObservationList extends StatelessWidget {
  const ObservationList(this.extraction, {super.key});
  final ExtractionResult extraction;
  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    Widget tile(String key, Map<String, dynamic> fields, String identity) =>
        ObservationTile(
          key: ValueKey('observation-$identity$key'),
          label: analysisLabel(s, key),
          observation: ExtractionField.fromJson(
            fields[key] as Map<String, dynamic>,
          ),
        );
    if (extraction.medicine != null) {
      return Column(
        children: [
          for (final key in medicineObservationKeys)
            tile(key, extraction.medicine!.toJson(), ''),
        ],
      );
    }
    final lines = [...extraction.lines]
      ..sort((a, b) => a.ordinal.compareTo(b.ordinal));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final line in lines) ...[
          AnalysisHeading('${s.analysisLine} ${line.ordinal + 1}'),
          for (final key in prescriptionObservationKeys)
            tile(key, line.fields.toJson(), '${line.lineId}.'),
        ],
      ],
    );
  }
}
