import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/providers.dart';
import 'medication_controller.dart';
import 'medication_service.dart';

final medicationServiceProvider = Provider(
  (ref) => MedicationService(ref.watch(apiProvider)),
);
final medicationControllerProvider =
    ChangeNotifierProvider.autoDispose<MedicationController>((ref) {
      ref.watch(
        accountProvider.select((account) => (account.userId, account.status)),
      );
      return MedicationController(
        ref.watch(medicationServiceProvider),
        () => ref.read(accountProvider).expire(),
      );
    });
