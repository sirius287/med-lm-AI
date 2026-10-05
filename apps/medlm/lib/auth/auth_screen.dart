import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../app/providers.dart';
import '../design_system/theme.dart';
import '../l10n/app_localizations.dart';
import 'auth_controller.dart';

class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key});
  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen>
    with WidgetsBindingObserver {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _passwordFocus = FocusNode();
  bool _register = false;
  bool _visible = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    Future.microtask(() {
      if (mounted) ref.read(accountProvider).restore();
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      ref.read(accountProvider).restore();
    } else {
      _password.clear();
      if (mounted) setState(() => _visible = false);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _email.dispose();
    _password.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final controller = ref.read(accountProvider);
    if (controller.busy || !_form.currentState!.validate()) return;
    final password = _password.text;
    _password.clear();
    setState(() => _visible = false);
    await controller.submit(_email.text.trim(), password, register: _register);
    if (mounted && !_register && controller.status == AccountStatus.signedIn) {
      GoRouter.maybeOf(context)?.go('/home');
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = AppLocalizations.of(context)!;
    final controller = ref.watch(accountProvider);
    final status = controller.status;
    return Scaffold(
      appBar: AppBar(
        title: Text(s.account),
        leading: IconButton(
          tooltip: s.home,
          onPressed: () => context.go('/home'),
          icon: const Icon(Icons.home_outlined),
        ),
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 600),
            child: ListView(
              padding: const EdgeInsets.all(24),
              children: [
                SoftPanel(
                  child: FocusTraversalGroup(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Semantics(
                          header: true,
                          child: Text(
                            status == AccountStatus.signedIn
                                ? s.signedIn
                                : s.account,
                            style: Theme.of(context).textTheme.headlineMedium,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(s.authScope),
                        const SizedBox(height: 24),
                        if (controller.busy) ...[
                          LinearProgressIndicator(
                            semanticsLabel: s.authWorking,
                          ),
                          const SizedBox(height: 16),
                        ],
                        if (controller.errorCode != null)
                          Semantics(
                            liveRegion: true,
                            child: Text(
                              controller.errorCode ==
                                      'remote_logout_unconfirmed'
                                  ? s.remoteLogoutUnconfirmed
                                  : controller.errorCode == 'session_expired'
                                  ? s.sessionExpired
                                  : controller.errorCode == 'rate_limited'
                                  ? s.authRateLimited
                                  : controller.errorCode ==
                                        'authentication_failed'
                                  ? (_register
                                        ? s.registrationFailed
                                        : s.authFailed)
                                  : s.authUnavailable,
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.error,
                              ),
                            ),
                          ),
                        if (status == AccountStatus.logoutUnconfirmed) ...[
                          Semantics(
                            liveRegion: true,
                            child: Text(s.logoutUnconfirmed),
                          ),
                          const SizedBox(height: 16),
                          FilledButton(
                            key: const Key('retry-logout'),
                            onPressed: controller.busy
                                ? null
                                : controller.logout,
                            child: Text(s.retry),
                          ),
                        ] else if (status == AccountStatus.unavailable) ...[
                          Text(
                            controller.available
                                ? s.sessionUnavailable
                                : s.authNotConfigured,
                          ),
                          if (controller.available)
                            FilledButton(
                              onPressed: controller.busy
                                  ? null
                                  : controller.restore,
                              child: Text(s.retry),
                            ),
                          if (controller.available)
                            OutlinedButton(
                              onPressed: controller.busy
                                  ? null
                                  : controller.logout,
                              child: Text(s.signOut),
                            ),
                        ] else if (status == AccountStatus.signedIn) ...[
                          Text(s.sessionVerified),
                          const SizedBox(height: 24),
                          FilledButton(
                            key: const Key('logout'),
                            onPressed: controller.busy
                                ? null
                                : controller.logout,
                            child: Text(s.signOut),
                          ),
                        ] else if (status != AccountStatus.initial) ...[
                          if (status == AccountStatus.checkEmail) ...[
                            Semantics(
                              liveRegion: true,
                              child: Text(s.checkEmail),
                            ),
                            const SizedBox(height: 16),
                          ],
                          Form(
                            key: _form,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                TextFormField(
                                  key: const Key('email'),
                                  controller: _email,
                                  enabled: !controller.busy,
                                  keyboardType: TextInputType.emailAddress,
                                  textInputAction: TextInputAction.next,
                                  autocorrect: false,
                                  autofillHints: const [AutofillHints.email],
                                  decoration: InputDecoration(
                                    labelText: s.email,
                                    errorMaxLines: 8,
                                  ),
                                  validator: (value) =>
                                      RegExp(
                                        r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
                                      ).hasMatch(value?.trim() ?? '')
                                      ? null
                                      : s.emailInvalid,
                                  onFieldSubmitted: (_) =>
                                      _passwordFocus.requestFocus(),
                                ),
                                const SizedBox(height: 20),
                                TextFormField(
                                  key: const Key('password'),
                                  controller: _password,
                                  focusNode: _passwordFocus,
                                  enabled: !controller.busy,
                                  obscureText: !_visible,
                                  autocorrect: false,
                                  enableSuggestions: false,
                                  keyboardType: TextInputType.visiblePassword,
                                  textInputAction: TextInputAction.done,
                                  decoration: InputDecoration(
                                    labelText: s.password,
                                    helperText: s.passwordRule,
                                    helperMaxLines: 4,
                                    errorMaxLines: 4,
                                    suffixIcon: IconButton(
                                      tooltip: _visible
                                          ? s.hidePassword
                                          : s.showPassword,
                                      onPressed: controller.busy
                                          ? null
                                          : () => setState(
                                              () => _visible = !_visible,
                                            ),
                                      icon: Icon(
                                        _visible
                                            ? Icons.visibility_off_outlined
                                            : Icons.visibility_outlined,
                                      ),
                                    ),
                                  ),
                                  validator: (value) =>
                                      (value?.runes.length ?? 0) >= 12 &&
                                          (value?.runes.length ?? 0) <= 128
                                      ? null
                                      : s.passwordRule,
                                  onFieldSubmitted: (_) => _submit(),
                                ),
                                const SizedBox(height: 24),
                                FilledButton(
                                  key: const Key('submit-auth'),
                                  onPressed: controller.busy ? null : _submit,
                                  child: Text(
                                    _register ? s.createAccount : s.signIn,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                OutlinedButton(
                                  key: const Key('toggle-auth'),
                                  onPressed: controller.busy
                                      ? null
                                      : () {
                                          _password.clear();
                                          _form.currentState?.reset();
                                          setState(() {
                                            _register = !_register;
                                            _visible = false;
                                          });
                                        },
                                  child: Text(
                                    _register
                                        ? s.useExistingAccount
                                        : s.createAccount,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
