import 'package:flutter_test/flutter_test.dart';
import 'package:medlm/analysis/generated/analysis_models.dart';
import 'package:medlm/analysis/generated/synthetic_fixture_catalog.dart';
import 'analysis_test_support.dart';

void main() {
  test(
    'generated report preserves all 24 null medical keys and literal observations',
    () {
      final model = AnalysisReport.fromJson(reportJson(ambiguous: true));
      expect(model.fields.keys.toSet(), medicalInformationKeys.toSet());
      expect(model.fields.length, 24);
      expect(model.fields.values.every((f) => f.value == null), isTrue);
      expect(model.observations.medicine!.medicine.rawText, ' TEST ITEM A ');
      expect(model.observations.medicine!.medicine.alternatives, [
        'TEST ITEM B',
      ]);
      expect(model.verificationStatus, 'unverified');
    },
  );
  test(
    'strict wire validation rejects missing, extra, typed and medical-value violations',
    () {
      final invalid = <Map<String, dynamic>>[
        reportJson()..remove('observations'),
        reportJson()..['clinical_truth'] = true,
        reportJson()..['revision'] = '1',
        reportJson()..['verified_at'] = '2026-10-15T10:00:00Z',
        reportJson()..['verification_status'] = 'verified',
      ];
      final nonnull = reportJson();
      nonnull['fields']['strength']['value'] = 'invented';
      invalid.add(nonnull);
      for (final json in invalid) {
        expect(() => AnalysisReport.fromJson(json), throwsFormatException);
      }
    },
  );
  test(
    'models defensively copy nested values and preserve prescription identities',
    () {
      final source = reportJson(prescription: true);
      final model = AnalysisReport.fromJson(source);
      source['observations']['lines'].clear();
      expect(model.observations.lines.map((line) => line.lineId), [
        firstLineId,
        secondLineId,
      ]);
      expect(
        model.observations.lines.first.fields.strength.rawText,
        'STRENGTH TOKEN',
      );
      expect(model.observations.lines.first.fields.dose.rawText, isNull);
      expect(() => model.observations.lines.clear(), throwsUnsupportedError);
      final copy = model.toJson();
      copy['fields'].clear();
      expect(model.fields.length, 24);
    },
  );
  test(
    'bundled catalog has only labelled synthetic controlled entries and fresh byte buffers',
    () {
      expect(bundledFixtures.length, 9);
      expect(bundledFixtures.map((f) => f.kind).toSet(), {
        'strip',
        'bottle',
        'tube',
        'box',
        'prescription',
      });
      for (final fixture in bundledFixtures) {
        expect(fixture.id, startsWith('synthetic_'));
        expect(fixture.mime, 'image/png');
        expect(fixture.revision, 1);
        final bytes = fixture.bytes();
        bytes.fillRange(0, bytes.length, 0);
        expect(fixture.bytes().take(4), [137, 80, 78, 71]);
      }
    },
  );
}
