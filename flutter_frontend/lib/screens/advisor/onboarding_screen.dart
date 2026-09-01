import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_frontend/models/onboarding_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/license_upload_sheet.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:flutter_frontend/theme/app_theme_controller.dart';

class AdvisorOnboardingScreen extends StatefulWidget {
  const AdvisorOnboardingScreen({
    super.key,
    required this.mandatory,
    required this.onCompleted,
    this.initialData,
    this.advisorRepository,
    this.authRepository,
    this.documentPicker,
  });

  final bool mandatory;
  final AdvisorOnboarding? initialData;
  final AdvisorRepository? advisorRepository;
  final AuthRepository? authRepository;
  final LicenseDocumentPicker? documentPicker;
  final ValueChanged<AdvisorOnboarding> onCompleted;

  @override
  State<AdvisorOnboardingScreen> createState() =>
      _AdvisorOnboardingScreenState();
}

class _AdvisorOnboardingScreenState extends State<AdvisorOnboardingScreen> {
  static const _pageCount = 6;
  static const _showRate = 33.33;

  late final AdvisorRepository _advisorRepository =
      widget.advisorRepository ?? AdvisorRepository();
  late final AuthRepository _authRepository =
      widget.authRepository ?? AuthRepository();
  final _pageController = PageController();

  AdvisorOnboarding? _data;
  var _page = 0;
  var _income = 250000.0;
  var _averageSale = 25000.0;
  var _commissionRate = 20.0;
  var _closingRate = 33.0;
  var _consentAccepted = false;
  var _loading = true;
  var _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final initial = widget.initialData;
    if (initial != null) {
      _applyData(initial);
      _loading = false;
    } else {
      _load();
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final data = await _advisorRepository.getOnboarding();
      if (!mounted) return;
      setState(() => _applyData(data));
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _applyData(AdvisorOnboarding data) {
    _data = data;
    _income = data.annualIncomeGoalCents / 100;
    _averageSale = data.averageSaleCents / 100;
    _commissionRate = data.commissionRateBps / 100;
    _closingRate = data.closingRateBps / 100;
    _consentAccepted = data.consentAccepted;
  }

  void _goTo(int page) {
    final next = page.clamp(0, _pageCount - 1);
    setState(() {
      _page = next;
      _error = null;
    });
    _pageController.animateToPage(
      next,
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
    );
  }

  Future<void> _openLicense() async {
    await showLicenseUploadSheet(
      context: context,
      repository: _authRepository,
      documentPicker: widget.documentPicker,
      rejectedLicense: _data?.rejectedLicense,
      onSubmitted: (_) {},
    );
    if (!mounted) return;
    try {
      final refreshed = await _advisorRepository.getOnboarding();
      if (mounted) setState(() => _applyData(refreshed));
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _finish() async {
    if (_saving) return;
    if (!_consentAccepted) {
      setState(() => _error = 'Accept the verification consent to continue.');
      return;
    }
    final status = _data?.licenseStatus ?? 'not_submitted';
    if (status != 'pending' && status != 'verified') {
      setState(() {
        _error = status == 'rejected'
            ? 'Resubmit the rejected license before continuing.'
            : 'Upload a license before continuing.';
      });
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final saved = await _advisorRepository.saveOnboarding(
        annualIncomeGoalCents: (_income * 100).round(),
        averageSaleCents: (_averageSale * 100).round(),
        commissionRateBps: (_commissionRate * 100).round(),
        closingRateBps: (_closingRate * 100).round(),
        consentAccepted: _consentAccepted,
      );
      if (!mounted) return;
      widget.onCompleted(saved);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  _PlanPreview get _plan {
    final averageCommission = math.max(
      1,
      _averageSale * (_commissionRate / 100),
    );
    final deals = (_income / averageCommission).ceil();
    final appointments = (deals / (_closingRate / 100)).ceil();
    final leads = (appointments / (_showRate / 100)).ceil();
    return _PlanPreview(
      averageCommission: averageCommission.round(),
      deals: deals,
      appointments: appointments,
      leads: leads,
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !widget.mandatory,
      child: Scaffold(
        backgroundColor: context.appCanvas,
        body: SafeArea(
          child: Column(
            children: [
              _OnboardingHeader(
                page: _page,
                pageCount: _pageCount,
                canClose: !widget.mandatory,
                onClose: () => Navigator.of(context).pop(),
              ),
              if (_loading)
                const Expanded(
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_data == null && _error != null)
                Expanded(
                  child: _LoadError(message: _error!, onRetry: _load),
                )
              else ...[
                Expanded(
                  child: PageView(
                    controller: _pageController,
                    physics: const NeverScrollableScrollPhysics(),
                    children: [
                      const _WelcomePage(),
                      _QuestionPage(
                        icon: Icons.savings_outlined,
                        eyebrow: 'Income by Design',
                        title: 'What is your desired NET yearly income?',
                        subtitle: 'Your personal take-home income goal.',
                        value: _income,
                        min: 50000,
                        max: 10000000,
                        step: 10000,
                        inputPrefix: '\$',
                        rangeLabel: '\$50k — \$10m',
                        onChanged: (value) => setState(() => _income = value),
                      ),
                      _QuestionPage(
                        icon: Icons.request_quote_outlined,
                        eyebrow: 'Your typical sale',
                        title: 'What is your average sale amount?',
                        subtitle: 'The typical policy size you write.',
                        value: _averageSale,
                        min: 1000,
                        max: 20000000,
                        step: 1000,
                        inputPrefix: '\$',
                        rangeLabel: '\$1k — \$20m',
                        onChanged: (value) =>
                            setState(() => _averageSale = value),
                      ),
                      _QuestionPage(
                        icon: Icons.percent_rounded,
                        eyebrow: 'Your earnings',
                        title: 'What is your average commission per sale?',
                        subtitle:
                            'The percentage you personally pocket on a typical deal.',
                        value: _commissionRate,
                        min: 1,
                        max: 50,
                        step: 1,
                        inputSuffix: '%',
                        rangeLabel: '1% — 50%',
                        onChanged: (value) =>
                            setState(() => _commissionRate = value),
                      ),
                      _QuestionPage(
                        icon: Icons.handshake_outlined,
                        eyebrow: 'Your conversion',
                        title: 'What percentage of appointments do you close?',
                        subtitle:
                            'Use your realistic appointment-to-deal closing rate.',
                        value: _closingRate,
                        min: 1,
                        max: 100,
                        step: 1,
                        inputSuffix: '%',
                        rangeLabel: '1% — 100%',
                        onChanged: (value) =>
                            setState(() => _closingRate = value),
                      ),
                      _ReviewPage(
                        plan: _plan,
                        income: _income.round(),
                        averageSale: _averageSale.round(),
                        commissionRate: _commissionRate.round(),
                        closingRate: _closingRate.round(),
                        data: _data!,
                        consentAccepted: _consentAccepted,
                        onConsentChanged: (value) =>
                            setState(() => _consentAccepted = value),
                        onLicense: _openLicense,
                      ),
                    ],
                  ),
                ),
                _BottomActions(
                  page: _page,
                  pageCount: _pageCount,
                  saving: _saving,
                  error: _error,
                  isEditing: !widget.mandatory,
                  onBack: () => _goTo(_page - 1),
                  onNext: _page == _pageCount - 1
                      ? _finish
                      : () async => _goTo(_page + 1),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _OnboardingHeader extends StatelessWidget {
  const _OnboardingHeader({
    required this.page,
    required this.pageCount,
    required this.canClose,
    required this.onClose,
  });

  final int page;
  final int pageCount;
  final bool canClose;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 10, 14, 8),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppColors.indigo, AppColors.cyan],
                  ),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: const Icon(
                  Icons.auto_graph,
                  color: Colors.white,
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Spectaculeads',
                  style: TextStyle(
                    color: context.appInk,
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const AppThemeToggleButton(),
              if (canClose)
                IconButton(
                  onPressed: onClose,
                  tooltip: 'Close onboarding',
                  icon: const Icon(Icons.close),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: List.generate(
              pageCount,
              (index) => Expanded(
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  height: 4,
                  margin: EdgeInsets.only(
                    right: index == pageCount - 1 ? 0 : 5,
                  ),
                  decoration: BoxDecoration(
                    color: index <= page ? AppColors.cyan : context.appOutline,
                    borderRadius: BorderRadius.circular(99),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _WelcomePage extends StatelessWidget {
  const _WelcomePage();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
      children: [
        const Center(
          child: Icon(
            Icons.rocket_launch_rounded,
            color: AppColors.cyan,
            size: 28,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'WELCOME ABOARD',
          style: TextStyle(
            color: AppColors.cyan,
            fontSize: 10,
            fontWeight: FontWeight.w900,
            letterSpacing: 1.4,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Let’s design your income',
          style: TextStyle(
            color: context.appInk,
            fontSize: 29,
            height: 1.05,
            fontWeight: FontWeight.w900,
            letterSpacing: -0.8,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Answer four quick questions, submit your license, and we’ll turn your income target into a clear pipeline plan.',
          style: TextStyle(color: context.appMuted, height: 1.45, fontSize: 15),
        ),
        const SizedBox(height: 26),
        const _WelcomeStep(
          number: '01',
          icon: Icons.edit_note_rounded,
          title: 'Share your targets',
          body: 'Tell us the income you want and how you sell.',
        ),
        const _WelcomeStep(
          number: '02',
          icon: Icons.map_outlined,
          title: 'Get your roadmap',
          body: 'We calculate the deals, appointments, and leads you need.',
        ),
        const _WelcomeStep(
          number: '03',
          icon: Icons.verified_user_outlined,
          title: 'Verify your license',
          body: 'Submit once, then continue while our team reviews it.',
        ),
      ],
    );
  }
}

class _WelcomeStep extends StatelessWidget {
  const _WelcomeStep({
    required this.number,
    required this.icon,
    required this.title,
    required this.body,
  });

  final String number;
  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 11),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: context.appSurface,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Row(
        children: [
          Container(
            width: 43,
            height: 43,
            decoration: BoxDecoration(
              color: context.appSoftFill,
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(icon, color: AppColors.cyan, size: 21),
          ),
          const SizedBox(width: 13),
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
                const SizedBox(height: 3),
                Text(
                  body,
                  style: TextStyle(color: context.appMuted, fontSize: 12.5),
                ),
              ],
            ),
          ),
          Text(
            number,
            style: TextStyle(
              color: context.appOutline,
              fontSize: 19,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _ThousandsSeparatorInputFormatter extends TextInputFormatter {
  const _ThousandsSeparatorInputFormatter();

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(RegExp(r'\D'), '');
    if (digits.isEmpty) return const TextEditingValue();
    final formatted = _groupDigits(digits);
    return TextEditingValue(
      text: formatted,
      selection: TextSelection.collapsed(offset: formatted.length),
    );
  }
}

String _groupDigits(String digits) {
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index++) {
    if (index > 0 && (digits.length - index) % 3 == 0) buffer.write(',');
    buffer.write(digits[index]);
  }
  return buffer.toString();
}

class _QuestionPage extends StatefulWidget {
  const _QuestionPage({
    required this.icon,
    required this.eyebrow,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.min,
    required this.max,
    required this.step,
    required this.rangeLabel,
    required this.onChanged,
    this.inputPrefix,
    this.inputSuffix,
  });

  final IconData icon;
  final String eyebrow;
  final String title;
  final String subtitle;
  final double value;
  final double min;
  final double max;
  final double step;
  final String rangeLabel;
  final ValueChanged<double> onChanged;
  final String? inputPrefix;
  final String? inputSuffix;

  @override
  State<_QuestionPage> createState() => _QuestionPageState();
}

class _QuestionPageState extends State<_QuestionPage> {
  late final TextEditingController _controller;
  late final FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: _editableValue(widget.value));
    _focusNode = FocusNode()..addListener(_handleFocusChanged);
  }

  @override
  void didUpdateWidget(covariant _QuestionPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_focusNode.hasFocus && oldWidget.value != widget.value) {
      _controller.text = _editableValue(widget.value);
    }
  }

  @override
  void dispose() {
    _focusNode
      ..removeListener(_handleFocusChanged)
      ..dispose();
    _controller.dispose();
    super.dispose();
  }

  String _editableValue(double value) => _groupDigits(value.round().toString());

  double? _parseEditable(String value) =>
      double.tryParse(value.replaceAll(',', ''));

  void _handleFocusChanged() {
    if (!_focusNode.hasFocus) _commitValue();
  }

  void _handleTextChanged(String text) {
    final parsed = _parseEditable(text);
    if (parsed != null && parsed >= widget.min && parsed <= widget.max) {
      widget.onChanged(parsed);
    }
  }

  void _commitValue() {
    final parsed = _parseEditable(_controller.text);
    final next = (parsed ?? widget.value).clamp(widget.min, widget.max);
    widget.onChanged(next);
    _controller.text = _editableValue(next);
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
      children: [
        Center(child: Icon(widget.icon, color: AppColors.cyan, size: 28)),
        const SizedBox(height: 8),
        Text(
          widget.eyebrow.toUpperCase(),
          style: const TextStyle(
            color: AppColors.cyan,
            fontSize: 10,
            fontWeight: FontWeight.w900,
            letterSpacing: 1.4,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          widget.title,
          style: TextStyle(
            color: context.appInk,
            fontSize: 25,
            height: 1.12,
            fontWeight: FontWeight.w900,
            letterSpacing: -.5,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          widget.subtitle,
          style: TextStyle(color: context.appMuted, fontSize: 14, height: 1.4),
        ),
        const SizedBox(height: 28),
        Container(
          padding: const EdgeInsets.fromLTRB(18, 22, 18, 16),
          decoration: BoxDecoration(
            color: context.appSurface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: context.appOutline),
            boxShadow: context.appCardShadows,
          ),
          child: Column(
            children: [
              Semantics(
                textField: true,
                label: '${widget.title} value',
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (widget.inputPrefix != null) ...[
                      Text(
                        widget.inputPrefix!,
                        style: const TextStyle(
                          color: AppColors.cyan,
                          fontSize: 30,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(width: 6),
                    ],
                    SizedBox(
                      width: widget.inputPrefix != null ? 190 : 105,
                      child: TextField(
                        key: ValueKey('onboarding-value-${widget.eyebrow}'),
                        controller: _controller,
                        focusNode: _focusNode,
                        keyboardType: TextInputType.number,
                        textInputAction: TextInputAction.done,
                        inputFormatters: const [
                          _ThousandsSeparatorInputFormatter(),
                        ],
                        textAlign: TextAlign.center,
                        onChanged: _handleTextChanged,
                        onSubmitted: (_) => _commitValue(),
                        style: const TextStyle(
                          color: AppColors.cyan,
                          fontSize: 34,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -1,
                        ),
                        decoration: const InputDecoration(
                          isDense: true,
                          filled: false,
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: UnderlineInputBorder(
                            borderSide: BorderSide(
                              color: AppColors.cyan,
                              width: 2,
                            ),
                          ),
                          contentPadding: EdgeInsets.symmetric(vertical: 4),
                        ),
                      ),
                    ),
                    if (widget.inputSuffix != null) ...[
                      const SizedBox(width: 5),
                      Text(
                        widget.inputSuffix!,
                        style: const TextStyle(
                          color: AppColors.cyan,
                          fontSize: 27,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Tap to type or drag to adjust',
                style: TextStyle(color: context.appMuted, fontSize: 12),
              ),
              const SizedBox(height: 15),
              Slider(
                value: widget.value.clamp(widget.min, widget.max),
                min: widget.min,
                max: widget.max,
                onChanged: (raw) {
                  final next = (raw / widget.step).round() * widget.step;
                  widget.onChanged(next);
                  _controller.text = _editableValue(next);
                },
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    widget.rangeLabel.split(' — ').first,
                    style: TextStyle(color: context.appMuted, fontSize: 11),
                  ),
                  Text(
                    widget.rangeLabel.split(' — ').last,
                    style: TextStyle(color: context.appMuted, fontSize: 11),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ReviewPage extends StatelessWidget {
  const _ReviewPage({
    required this.plan,
    required this.income,
    required this.averageSale,
    required this.commissionRate,
    required this.closingRate,
    required this.data,
    required this.consentAccepted,
    required this.onConsentChanged,
    required this.onLicense,
  });

  final _PlanPreview plan;
  final int income;
  final int averageSale;
  final int commissionRate;
  final int closingRate;
  final AdvisorOnboarding data;
  final bool consentAccepted;
  final ValueChanged<bool> onConsentChanged;
  final VoidCallback onLicense;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
      children: [
        const Center(
          child: Icon(Icons.route_outlined, color: AppColors.cyan, size: 28),
        ),
        const SizedBox(height: 8),
        const Text(
          'YOUR ROADMAP',
          style: TextStyle(
            color: AppColors.cyan,
            fontSize: 10,
            fontWeight: FontWeight.w900,
            letterSpacing: 1.4,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Your plan is ready',
          style: TextStyle(
            color: context.appInk,
            fontSize: 25,
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppColors.indigo, Color(0xFF087F91)],
            ),
            borderRadius: BorderRadius.circular(20),
            boxShadow: context.appCardShadows,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'PROJECTED ANNUAL INCOME',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: .68),
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                _money(income.toDouble()),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 30,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 15),
              Row(
                children: [
                  _PlanMetric(value: '${plan.deals}', label: 'deals'),
                  _PlanMetric(
                    value: '${plan.appointments}',
                    label: 'appointments',
                  ),
                  _PlanMetric(value: '${plan.leads}', label: 'leads'),
                ],
              ),
              const SizedBox(height: 13),
              Text(
                '${_money(plan.averageCommission.toDouble())} average commission per deal · 33% lead show rate',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: .75),
                  fontSize: 11.5,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        _LicenseStatusCard(data: data, onAction: onLicense),
        const SizedBox(height: 12),
        Material(
          color: context.appSurface,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: context.appOutline),
            ),
            child: CheckboxListTile(
              value: consentAccepted,
              onChanged: (value) => onConsentChanged(value ?? false),
              controlAffinity: ListTileControlAffinity.leading,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              title: Text(
                'Verification consent',
                style: TextStyle(
                  color: context.appInk,
                  fontWeight: FontWeight.w900,
                ),
              ),
              subtitle: Text(
                'I confirm these details are accurate and consent to license verification.',
                style: TextStyle(color: context.appMuted, fontSize: 11.5),
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Captured: ${_money(averageSale.toDouble())} average sale · $commissionRate% commission · $closingRate% closing rate',
          style: TextStyle(color: context.appMuted, fontSize: 11.5),
        ),
      ],
    );
  }
}

class _PlanMetric extends StatelessWidget {
  const _PlanMetric({required this.value, required this.label});
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 21,
              fontWeight: FontWeight.w900,
            ),
          ),
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withValues(alpha: .62),
              fontSize: 10.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _LicenseStatusCard extends StatelessWidget {
  const _LicenseStatusCard({required this.data, required this.onAction});
  final AdvisorOnboarding data;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    final status = data.licenseStatus;
    final isPending = status == 'pending';
    final isVerified = status == 'verified';
    final isRejected = status == 'rejected';
    final color = isVerified
        ? const Color(0xFF059669)
        : isRejected
        ? const Color(0xFFDC2626)
        : isPending
        ? const Color(0xFFF59E0B)
        : AppColors.cyan;
    final title = isVerified
        ? 'License verified'
        : isRejected
        ? 'License needs attention'
        : isPending
        ? 'License in review'
        : 'Submit your license';
    final body = isVerified
        ? 'You can purchase leads in your verified state.'
        : isRejected
        ? data.rejectedLicense?.rejectionReason ??
              'Upload a corrected document for another review.'
        : isPending
        ? 'You can continue. We’ll notify you when the review is complete.'
        : 'A PDF or image is required to complete onboarding.';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: context.isDarkMode ? .13 : .08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: .35)),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withValues(alpha: .13),
              shape: BoxShape.circle,
            ),
            child: Icon(
              isRejected
                  ? Icons.error_outline
                  : isVerified
                  ? Icons.verified_outlined
                  : Icons.policy_outlined,
              color: color,
            ),
          ),
          const SizedBox(width: 12),
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
                const SizedBox(height: 3),
                Text(
                  body,
                  style: TextStyle(color: context.appMuted, fontSize: 11.5),
                ),
              ],
            ),
          ),
          if (!isVerified && !isPending)
            TextButton(
              onPressed: onAction,
              child: Text(isRejected ? 'Resubmit' : 'Upload'),
            ),
        ],
      ),
    );
  }
}

class _BottomActions extends StatelessWidget {
  const _BottomActions({
    required this.page,
    required this.pageCount,
    required this.saving,
    required this.error,
    required this.isEditing,
    required this.onBack,
    required this.onNext,
  });
  final int page;
  final int pageCount;
  final bool saving;
  final String? error;
  final bool isEditing;
  final VoidCallback onBack;
  final Future<void> Function() onNext;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 10, 18, 14),
      decoration: BoxDecoration(
        color: context.appSurface,
        border: Border(top: BorderSide(color: context.appOutline)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (error != null) ...[
            Text(
              error!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFFDC2626), fontSize: 12),
            ),
            const SizedBox(height: 8),
          ],
          Row(
            children: [
              if (page > 0) ...[
                SizedBox.square(
                  dimension: 48,
                  child: OutlinedButton(
                    onPressed: saving ? null : onBack,
                    style: OutlinedButton.styleFrom(
                      padding: EdgeInsets.zero,
                      side: BorderSide(color: context.appOutline),
                    ),
                    child: const Icon(Icons.arrow_back_rounded, size: 20),
                  ),
                ),
                const SizedBox(width: 10),
              ],
              Expanded(
                child: SizedBox(
                  height: 48,
                  child: FilledButton.icon(
                    onPressed: saving ? null : onNext,
                    icon: saving
                        ? const SizedBox.square(
                            dimension: 17,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Icon(
                            page == pageCount - 1
                                ? Icons.rocket_launch_rounded
                                : Icons.arrow_forward,
                          ),
                    label: Text(
                      saving
                          ? 'Saving your plan…'
                          : page == 0
                          ? 'Start my plan'
                          : page == pageCount - 1
                          ? isEditing
                                ? 'Save changes'
                                : 'Continue to Buy Leads'
                          : 'Next',
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _LoadError extends StatelessWidget {
  const _LoadError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off_outlined, color: context.appMuted, size: 42),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(color: context.appMuted),
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}

class _PlanPreview {
  const _PlanPreview({
    required this.averageCommission,
    required this.deals,
    required this.appointments,
    required this.leads,
  });
  final int averageCommission;
  final int deals;
  final int appointments;
  final int leads;
}

String _money(double value) {
  final rounded = value.round();
  final digits = rounded.toString();
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index++) {
    if (index > 0 && (digits.length - index) % 3 == 0) buffer.write(',');
    buffer.write(digits[index]);
  }
  return '\$$buffer';
}
