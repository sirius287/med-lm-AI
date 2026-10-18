import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/analysis/analysis_validation.dart';
import 'package:medlm/analysis/generated/analysis_models.dart';
import 'analysis_test_support.dart';

void main() {
  test('missing observations cannot supply normalized values or units', () {
    final data = observationSet();
    data['medicine']['strength']['normalized_value'] = 'invented';
    expect(
      () => observedFields(ExtractionResult.fromJson(data)),
      throwsFormatException,
    );
  });
  test(
    'malformed locations and duplicate prescription identities are rejected',
    () {
      final located = observationSet();
      located['medicine']['medicine']['bounding_box'] = {
        'x': 0.8,
        'y': 0.1,
        'width': 0.5,
        'height': 0.2,
      };
      expect(
        () => observedFields(ExtractionResult.fromJson(located)),
        throwsFormatException,
      );
      final lines = observationSet(prescription: true);
      lines['lines'][1]['line_id'] = firstLineId;
      expect(
        () => observedFields(ExtractionResult.fromJson(lines)),
        throwsFormatException,
      );
    },
  );
  test(
    'confirmation requires exact whitespace and complete field coverage',
    () {
      final observations = ExtractionResult.fromJson(observationSet());
      final values = observedFields(observations);
      final body = {
        'version': 2,
        'revision': 1,
        'candidate_set_id': candidateSetId,
        'candidate_id': null,
        'decision': 'confirm',
        'line_dispositions': <String, dynamic>{},
        'fields': <String, dynamic>{
          for (final entry in values.entries)
            entry.key: {
              'status': 'confirmed',
              'reviewed_value': entry.value.rawText,
            },
        },
      };
      expect(
        validateHumanReview(
          HumanReview.fromJson(body),
          observations,
        )['medicine'],
        ' TEST ITEM A ',
      );
      final fields = body['fields'] as Map<String, dynamic>;
      fields['medicine']['reviewed_value'] = 'TEST ITEM A';
      expect(
        () => validateHumanReview(HumanReview.fromJson(body), observations),
        throwsFormatException,
      );
      fields['medicine']['reviewed_value'] = ' TEST ITEM A ';
      fields['extra'] = {'status': 'confirmed', 'reviewed_value': null};
      expect(
        () => validateHumanReview(HumanReview.fromJson(body), observations),
        throwsFormatException,
      );
    },
  );
}
