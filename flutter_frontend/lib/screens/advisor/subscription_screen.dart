import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/models/onboarding_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/onboarding_screen.dart';
import 'package:flutter_frontend/theme/app_components.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:url_launcher/url_launcher.dart';

typedef CheckoutUrlLauncher = Future<bool> Function(Uri url);

class SubscriptionScreen extends StatefulWidget {
  const SubscriptionScreen({
    super.key,
    this.repository,
    this.checkoutUrlLauncher,
  });

  final AdvisorRepository? repository;
  final CheckoutUrlLauncher? checkoutUrlLauncher;

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen>
    with WidgetsBindingObserver {
  late final AdvisorRepository _repository =
      widget.repository ?? AdvisorRepository();
  final AuthRepository _authRepository = AuthRepository();
  late Future<_BuyData> _future;
  int? _selectedPackageId;
  final Set<String> _selectedStates = {};
  bool _saving = false;
  bool _checkingPurchase = false;
  String? _error;
  String? _checkoutNotice;
  PurchaseCheckoutSession? _activeCheckout;
  Timer? _checkoutPollTimer;
  int _checkoutPollAttempt = 0;
  String? _checkoutRetryToken;

  static const _checkoutPollInterval = Duration(milliseconds: 1500);
  static const _maxCheckoutPollAttempts = 40;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _future = _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _checkoutPollTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _activeCheckout != null) {
      unawaited(_checkPurchaseStatus());
    }
  }

  Future<_BuyData> _load() async {
    final packages = await _repository.getPackages();
    final summary = await _repository.getDashboardSummary();
    final onboarding = await _repository.getOnboarding();
    final data = _BuyData(
      packages: packages,
      summary: summary,
      onboarding: onboarding,
    );
    _selectedStates.addAll(data.summary.targetStates);
    return data;
  }

  Future<void> _reviewOnboarding(AdvisorOnboarding onboarding) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => AdvisorOnboardingScreen(
          mandatory: false,
          initialData: onboarding,
          advisorRepository: _repository,
          authRepository: _authRepository,
          onCompleted: (_) => Navigator.of(context).pop(),
        ),
      ),
    );
    if (!mounted) return;
    setState(() => _future = _load());
  }

  Future<void> _continueToCheckout(_BuyData data) async {
    if (_saving) return;
    final selectedPackage = data.packages
        .where((item) => item.id == _selectedPackageId)
        .firstOrNull;
    if (selectedPackage == null) {
      setState(() => _error = 'Select a lead package.');
      return;
    }
    if (_selectedStates.isEmpty) {
      setState(() => _error = 'Select at least one target state.');
      return;
    }
    if (selectedPackage.stateLimit != null &&
        _selectedStates.length > selectedPackage.stateLimit!) {
      setState(
        () => _error =
            '${selectedPackage.name} supports up to '
            '${selectedPackage.stateLimit} target states.',
      );
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      _checkoutRetryToken ??=
          'mobile:${selectedPackage.id}:'
          '${DateTime.now().microsecondsSinceEpoch}';
      final checkout = await _repository.createPurchaseCheckout(
        packageId: selectedPackage.id,
        targetStates: _selectedStates.toList()..sort(),
        retryToken: _checkoutRetryToken,
      );
      if (checkout.demoMode) {
        if (!mounted) return;
        setState(() {
          _activeCheckout = checkout;
          _checkoutNotice =
              'Demo checkout completed — no payment was charged. '
              'Confirming your lead credits now.';
          _checkoutPollAttempt = 0;
        });
        await _checkPurchaseStatus();
        return;
      }
      final launcher =
          widget.checkoutUrlLauncher ??
          (url) => launchUrl(url, mode: LaunchMode.externalApplication);
      if (!await launcher(checkout.url)) {
        throw StateError('Unable to open secure checkout.');
      }
      if (!mounted) return;
      setState(() {
        _activeCheckout = checkout;
        _checkoutNotice =
            'Checkout opened securely. Return here after payment to confirm '
            'your lead credits.';
        _checkoutPollAttempt = 0;
      });
      _schedulePurchaseStatusCheck();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _schedulePurchaseStatusCheck() {
    _checkoutPollTimer?.cancel();
    if (_activeCheckout == null ||
        _checkoutPollAttempt >= _maxCheckoutPollAttempts) {
      return;
    }
    _checkoutPollTimer = Timer(
      _checkoutPollInterval,
      () => unawaited(_checkPurchaseStatus()),
    );
  }

  Future<void> _checkPurchaseStatus() async {
    final checkout = _activeCheckout;
    if (checkout == null || _checkingPurchase) return;
    _checkoutPollTimer?.cancel();
    setState(() => _checkingPurchase = true);
    try {
      final purchase = await _repository.getPurchaseByCheckoutSession(
        checkout.sessionId,
      );
      if (!mounted) return;
      if (purchase == null || purchase.status.toLowerCase() == 'pending') {
        setState(() {
          _checkoutNotice =
              'Payment is still being confirmed. Lead credits will appear '
              'automatically after Stripe confirms the purchase.';
          _checkoutPollAttempt += 1;
        });
        _schedulePurchaseStatusCheck();
        return;
      }
      if (purchase.isCompleted) {
        _checkoutPollTimer?.cancel();
        setState(() {
          _activeCheckout = null;
          _checkoutRetryToken = null;
          _selectedPackageId = null;
          _checkoutNotice =
              'Purchase complete. ${purchase.creditsTotal} lead credits '
              'were added${purchase.packageName == null ? '' : ' for ${purchase.packageName}'}.';
        });
        return;
      }
      if (purchase.isTerminalFailure) {
        _checkoutPollTimer?.cancel();
        setState(() {
          _activeCheckout = null;
          _checkoutRetryToken = null;
          _checkoutNotice =
              'Checkout ${purchase.status.toLowerCase()}. No new lead credits '
              'were added.';
        });
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _checkoutNotice =
            'We could not confirm the purchase yet. You can check again '
            'without being charged twice.';
        _checkoutPollAttempt += 1;
      });
      _schedulePurchaseStatusCheck();
    } finally {
      if (mounted) setState(() => _checkingPurchase = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_BuyData>(
      future: _future,
      builder: (context, snapshot) {
        return ListView(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 18),
          children: [
            const AppScreenHeader(
              eyebrow: 'Grow your pipeline',
              title: 'Buy Leads',
              subtitle: 'Choose a package and target the states that matter.',
              icon: Icons.shopping_bag_rounded,
            ),
            const SizedBox(height: 11),
            if (snapshot.connectionState == ConnectionState.waiting)
              const Center(child: CircularProgressIndicator())
            else if (snapshot.hasError)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(snapshot.error.toString()),
                ),
              )
            else ...[
              _LicenseReviewBanner(
                onboarding: snapshot.data!.onboarding,
                onReview: () => _reviewOnboarding(snapshot.data!.onboarding),
              ),
              const SizedBox(height: 10),
              _TargetStates(
                states: snapshot.data!.summary.targetStates,
                selectedStates: _selectedStates,
                onToggle: (state) {
                  setState(() {
                    if (_selectedStates.contains(state)) {
                      _selectedStates.remove(state);
                    } else {
                      _selectedStates.add(state);
                    }
                  });
                },
              ),
              const SizedBox(height: 10),
              for (final package in snapshot.data!.packages)
                Padding(
                  padding: const EdgeInsets.only(bottom: 9),
                  child: _PackageCard(
                    package: package,
                    selected: _selectedPackageId == package.id,
                    saving: _saving,
                    onTap: () {
                      setState(() {
                        _selectedPackageId = package.id;
                        _error = null;
                      });
                    },
                    onCheckout: () => _continueToCheckout(snapshot.data!),
                  ),
                ),
              if (_checkoutNotice != null) ...[
                Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: context.appSoftFill,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: const Color(0xFF9BDCE8)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _checkoutNotice!,
                        style: TextStyle(color: context.appMuted),
                      ),
                      if (_activeCheckout != null) ...[
                        const SizedBox(height: 8),
                        TextButton.icon(
                          onPressed: _checkingPurchase
                              ? null
                              : _checkPurchaseStatus,
                          icon: _checkingPurchase
                              ? const SizedBox.square(
                                  dimension: 14,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.refresh, size: 18),
                          label: const Text('Check purchase status'),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 2),
                Text(_error!, style: const TextStyle(color: Color(0xFFB91C1C))),
                const SizedBox(height: 10),
              ],
            ],
          ],
        );
      },
    );
  }
}

class _BuyData {
  _BuyData({
    required this.packages,
    required this.summary,
    required this.onboarding,
  });

  final List<LeadPackage> packages;
  final LeadDashboardSummary summary;
  final AdvisorOnboarding onboarding;
}

class _LicenseReviewBanner extends StatelessWidget {
  const _LicenseReviewBanner({
    required this.onboarding,
    required this.onReview,
  });

  final AdvisorOnboarding onboarding;
  final VoidCallback onReview;

  @override
  Widget build(BuildContext context) {
    final rejected = onboarding.licenseStatus == 'rejected';
    final pending = onboarding.licenseStatus == 'pending';
    final color = rejected
        ? const Color(0xFFDC2626)
        : pending
        ? const Color(0xFFF59E0B)
        : const Color(0xFF059669);
    final title = rejected
        ? 'License rejected — action required'
        : pending
        ? 'License is in review'
        : 'License verified';
    final description = rejected
        ? onboarding.rejectedLicense?.rejectionReason ??
              'Review the decision and resubmit your document.'
        : pending
        ? 'Your answers are saved. We’ll notify you after verification.'
        : 'Your onboarding plan and license are ready.';

    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: color.withValues(alpha: context.isDarkMode ? .14 : .07),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: .3)),
        boxShadow: context.appCardShadows,
      ),
      child: Row(
        children: [
          Container(
            width: 39,
            height: 39,
            decoration: BoxDecoration(
              color: color.withValues(alpha: .13),
              shape: BoxShape.circle,
            ),
            child: Icon(
              rejected
                  ? Icons.error_outline
                  : pending
                  ? Icons.hourglass_top_rounded
                  : Icons.verified_outlined,
              color: color,
              size: 21,
            ),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: context.appInk,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  description,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(color: context.appMuted, fontSize: 11),
                ),
              ],
            ),
          ),
          TextButton(
            onPressed: onReview,
            child: Text(rejected ? 'Fix now' : 'Review'),
          ),
        ],
      ),
    );
  }
}

class _TargetStates extends StatelessWidget {
  const _TargetStates({
    required this.states,
    required this.selectedStates,
    required this.onToggle,
  });

  final List<String> states;
  final Set<String> selectedStates;
  final ValueChanged<String> onToggle;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: context.appSurface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Target States',
              style: TextStyle(
                color: context.appInk,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 9),
            if (states.isEmpty)
              Text(
                'Add and verify a license before selecting target states.',
                style: TextStyle(color: context.appMuted),
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 7,
                children: [
                  for (final state in states)
                    _StateChip(
                      state: state,
                      selected: selectedStates.contains(state),
                      onTap: () => onToggle(state),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _StateChip extends StatelessWidget {
  const _StateChip({
    required this.state,
    required this.selected,
    required this.onTap,
  });

  final String state;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: context.appSurface,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          constraints: const BoxConstraints(minWidth: 54),
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected ? const Color(0xFF078AA2) : context.appOutline,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (selected) ...[
                const Icon(Icons.check, color: Color(0xFF078AA2), size: 14),
                const SizedBox(width: 5),
              ],
              Text(
                state,
                style: TextStyle(
                  color: selected ? const Color(0xFF078AA2) : context.appMuted,
                  fontSize: 12,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PackageCard extends StatelessWidget {
  const _PackageCard({
    required this.package,
    required this.selected,
    required this.saving,
    required this.onTap,
    required this.onCheckout,
  });

  final LeadPackage package;
  final bool selected;
  final bool saving;
  final VoidCallback onTap;
  final VoidCallback onCheckout;

  @override
  Widget build(BuildContext context) {
    final badge = _packageBadge(package);

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      decoration: BoxDecoration(
        color: selected
            ? (context.isDarkMode
                  ? const Color(0xFF142A3D)
                  : const Color(0xFFF4FDFF))
            : context.appSurface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: selected ? const Color(0xFF27B7CE) : context.appOutline,
          width: selected ? 1.6 : 1,
        ),
        boxShadow: context.appCardShadows,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  selected ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: selected
                      ? const Color(0xFF18A0B8)
                      : const Color(0xFFC7D7DD),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              package.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: context.appInk,
                                fontSize: 16,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '${package.creditsTotal} leads',
                            style: TextStyle(color: context.appMuted),
                          ),
                        ],
                      ),
                      const SizedBox(height: 5),
                      Text(
                        package.stateLimit == null
                            ? 'All verified states'
                            : 'Up to ${package.stateLimit} target states',
                        style: TextStyle(color: context.appMuted),
                      ),
                      const SizedBox(height: 9),
                      Text(
                        _money(package.priceCents),
                        style: TextStyle(
                          color: selected
                              ? const Color(0xFF18A0B8)
                              : context.appInk,
                          fontSize: 24,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      Row(
                        children: [
                          Text(
                            '${_money(package.costPerLeadCents)}/lead',
                            style: TextStyle(color: context.appMuted),
                          ),
                          if (badge != null) ...[
                            const Spacer(),
                            _PackageBadge(label: badge),
                          ],
                        ],
                      ),
                      if (selected) ...[
                        const SizedBox(height: 14),
                        SizedBox(
                          width: double.infinity,
                          height: 44,
                          child: FilledButton.icon(
                            onPressed: saving ? null : onCheckout,
                            style: FilledButton.styleFrom(
                              backgroundColor: const Color(0xFF18A0B8),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                            icon: saving
                                ? const SizedBox.square(
                                    dimension: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(Icons.lock_outline, size: 17),
                            label: Text(
                              saving
                                  ? 'Preparing checkout...'
                                  : 'Continue to checkout',
                            ),
                          ),
                        ),
                        const SizedBox(height: 7),
                        Center(
                          child: Text(
                            'Secure checkout • Cancel anytime',
                            style: TextStyle(
                              color: context.appMuted,
                              fontSize: 10.5,
                            ),
                          ),
                        ),
                      ],
                    ],
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

class _PackageBadge extends StatelessWidget {
  const _PackageBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFFE8FBFF),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Color(0xFF18A0B8),
          fontSize: 10,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

String? _packageBadge(LeadPackage package) {
  final name = package.name.toLowerCase();
  if (name.contains('pro')) return 'Recommended';
  if (name.contains('elite') || name.contains('unlimited')) return 'Most Leads';
  return null;
}

String _money(int cents) => '\$${(cents / 100).round()}';
