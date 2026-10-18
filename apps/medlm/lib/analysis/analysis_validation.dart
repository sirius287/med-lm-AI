import 'generated/analysis_models.dart';

Never invalidAnalysis() =>
    throw const FormatException('Invalid synthetic analysis response');

bool sameAnalysisJson(dynamic left, dynamic right) {
  if (left is Map && right is Map) {
    return left.length == right.length &&
        left.keys.every(
          (key) =>
              right.containsKey(key) && sameAnalysisJson(left[key], right[key]),
        );
  }
  if (left is List && right is List) {
    return left.length == right.length &&
        List.generate(
          left.length,
          (i) => i,
        ).every((i) => sameAnalysisJson(left[i], right[i]));
  }
  return left == right;
}

Map<String, ExtractionField> observedFields(ExtractionResult extraction) {
  if (extraction.documentKind == 'prescription') {
    if (extraction.medicine != null ||
        extraction.lines.map((line) => line.lineId).toSet().length !=
            extraction.lines.length ||
        extraction.lines.map((line) => line.ordinal).toSet().length !=
            extraction.lines.length) {
      invalidAnalysis();
    }
    return checkedObservations({
      for (final line in extraction.lines)
        for (final key in prescriptionObservationKeys)
          '${line.lineId}.$key': ExtractionField.fromJson(
            line.fields.toJson()[key] as Map<String, dynamic>,
          ),
    });
  }
  if (extraction.medicine == null || extraction.lines.isNotEmpty) {
    invalidAnalysis();
  }
  return checkedObservations({
    for (final key in medicineObservationKeys)
      key: ExtractionField.fromJson(
        extraction.medicine!.toJson()[key] as Map<String, dynamic>,
      ),
  });
}

Map<String, ExtractionField> checkedObservations(
  Map<String, ExtractionField> fields,
) {
  for (final field in fields.values) {
    if (field.rawText == null &&
        (field.normalizedValue != null || field.unit != null)) {
      invalidAnalysis();
    }
    if (field.rawText != null && field.rawText!.trim().isEmpty) {
      invalidAnalysis();
    }
    if (field.alternatives.isNotEmpty && field.ambiguityReason == null) {
      invalidAnalysis();
    }
    final box = field.boundingBox;
    if (box != null && (box.x + box.width > 1 || box.y + box.height > 1)) {
      invalidAnalysis();
    }
  }
  return fields;
}

Map<String, String?> validateHumanReview(
  HumanReview body,
  ExtractionResult extraction,
) {
  final expected = observedFields(extraction);
  final lineIds = extraction.lines.map((line) => line.lineId).toSet();
  if (!sameKeySet(body.fields.keys, expected.keys) ||
      !sameKeySet(body.lineDispositions.keys, lineIds)) {
    invalidAnalysis();
  }
  final selected = <String>{};
  for (final entry in body.fields.entries) {
    final field = entry.value;
    if (field.status == 'confirmed' &&
        field.reviewedValue != expected[entry.key]!.rawText) {
      invalidAnalysis();
    }
    if (['unreviewed', 'unresolved'].contains(field.status) &&
        field.reviewedValue != null) {
      invalidAnalysis();
    }
    final included =
        lineIds.isEmpty ||
        body.lineDispositions[entry.key.split('.').first] == 'included';
    if (included) {
      selected.add(field.status);
      if (lineIds.isNotEmpty &&
          !['confirmed', 'corrected'].contains(field.status)) {
        invalidAnalysis();
      }
    }
  }
  if (body.decision == 'confirm' && !sameKeySet(selected, ['confirmed'])) {
    invalidAnalysis();
  }
  if (body.decision == 'correct' &&
      (!selected.contains('corrected') ||
          !selected.every(['confirmed', 'corrected'].contains))) {
    invalidAnalysis();
  }
  if (!['confirm', 'correct'].contains(body.decision)) return {};
  return {
    for (final entry in body.fields.entries)
      if (lineIds.isEmpty ||
          body.lineDispositions[entry.key.split('.').first] == 'included')
        entry.key: entry.value.reviewedValue,
  };
}

bool sameKeySet(Iterable<String> a, Iterable<String> b) =>
    a.length == b.length && a.toSet().containsAll(b);

void validateSyntheticReport(AnalysisReport report) {
  // This harness has no source integration. Never render a medical value, badge
  // or synthetic descriptor as authoritative evidence, even from malformed JSON.
  if (!sameKeySet(report.fields.keys, medicalInformationKeys) ||
      report.evidence.isNotEmpty ||
      report.fields.values.any(
        (field) =>
            field.status != 'unavailable' ||
            field.reason != 'no_authoritative_source_checked' ||
            field.evidenceRefs.isNotEmpty,
      )) {
    invalidAnalysis();
  }
  final expected = observedFields(report.observations);
  final conflicts = [
    for (final entry in expected.entries)
      if (entry.value.ambiguityReason != null)
        {
          'field_key': entry.key,
          'raw_text': entry.value.rawText,
          'alternatives': entry.value.alternatives,
          'ambiguity_reason': entry.value.ambiguityReason,
        },
  ];
  if (!sameAnalysisJson(
    conflicts,
    report.observationConflicts.map((c) => c.toJson()).toList(),
  )) {
    invalidAnalysis();
  }
  var previous = 0;
  var closed = false;
  String? candidateSet;
  Map<String, String?> accepted = {};
  for (final item in report.reviewHistory) {
    final review = item.review;
    if (closed ||
        review.revision != report.revision ||
        review.version <= previous ||
        review.version >= report.analysisVersion ||
        (candidateSet != null && candidateSet != review.candidateSetId)) {
      invalidAnalysis();
    }
    accepted = validateHumanReview(review, report.observations);
    previous = review.version;
    candidateSet = review.candidateSetId;
    closed = review.decision != 'unresolved';
  }
  if (report.reviewState !=
          (report.reviewHistory.lastOrNull?.review.decision ?? 'unreviewed') ||
      !sameAnalysisJson(accepted, report.acceptedTranscription)) {
    invalidAnalysis();
  }
}
