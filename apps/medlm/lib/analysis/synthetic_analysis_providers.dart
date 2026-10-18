import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/providers.dart';
import '../auth/auth_controller.dart';
import 'synthetic_analysis_controller.dart';
import 'synthetic_analysis_service.dart';

/// Deliberately has no normal-app default or environment enable switch.
final syntheticAnalysisServiceProvider = Provider<SyntheticAnalysisService>(
  (ref) => throw StateError(
    'Explicit synthetic analysis service injection is required',
  ),
  dependencies: const [],
);

final syntheticAnalysisControllerProvider =
    ChangeNotifierProvider.autoDispose<SyntheticAnalysisController>((ref) {
      // Owner changes dispose the controller; transient same-owner revalidation
      // locks it without destroying unsent input or frozen replay keys/bodies.
      final owner = ref.watch(accountProvider.select((a) => a.userId));
      final controller = SyntheticAnalysisController(
        ref.watch(syntheticAnalysisServiceProvider),
        () => ref.read(accountProvider).expire(),
      );
      ref.listen(
        accountProvider.select((a) => (a.userId, a.status, a.busy)),
        (_, account) => controller.updateAuthorization(
          authenticated:
              owner != null &&
              account.$1 == owner &&
              account.$2 == AccountStatus.signedIn &&
              !account.$3,
          revalidating:
              owner != null &&
              account.$1 == owner &&
              account.$2 == AccountStatus.initial &&
              account.$3,
        ),
        fireImmediately: true,
      );
      return controller;
    }, dependencies: [syntheticAnalysisServiceProvider, accountProvider]);
