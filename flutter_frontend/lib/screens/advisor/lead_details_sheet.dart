import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:url_launcher/url_launcher.dart';

Future<void> showLeadDetailsSheet({
  required BuildContext context,
  required AdvisorLead lead,
  required AdvisorRepository repository,
  required ValueChanged<AdvisorLead> onUpdated,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    barrierColor: Colors.black.withValues(alpha: .5),
    showDragHandle: false,
    builder: (sheetContext) => FractionallySizedBox(
      heightFactor: 0.93,
      child: Container(
        decoration: BoxDecoration(
          color: sheetContext.appSurface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          border: Border(top: BorderSide(color: sheetContext.appOutline)),
        ),
        clipBehavior: Clip.antiAlias,
        child: LeadDetailsSheet(
          lead: lead,
          repository: repository,
          onUpdated: onUpdated,
        ),
      ),
    ),
  );
}

class LeadDetailsSheet extends StatefulWidget {
  const LeadDetailsSheet({
    super.key,
    required this.lead,
    required this.repository,
    required this.onUpdated,
  });

  final AdvisorLead lead;
  final AdvisorRepository repository;
  final ValueChanged<AdvisorLead> onUpdated;

  @override
  State<LeadDetailsSheet> createState() => _LeadDetailsSheetState();
}

class _LeadDetailsSheetState extends State<LeadDetailsSheet> {
  static const _statuses = <String, String>{
    'contacted': 'Contacted',
    'appointment_set': 'Appointment Set',
    'closed_deal': 'Closed Deal',
  };

  late AdvisorLead _lead = widget.lead;
  late final TextEditingController _notesController = TextEditingController(
    text: widget.lead.outcomeNotes ?? '',
  );
  late String? _status = _statuses.containsKey(widget.lead.outcomeStatus)
      ? widget.lead.outcomeStatus
      : null;
  bool _saving = false;
  String? _error;
  String? _success;

  bool get _canUpdate => _lead.piiUnlocked || _lead.isDownloaded;

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final status = _status;
    if (!_canUpdate || status == null || _saving) return;

    setState(() {
      _saving = true;
      _error = null;
      _success = null;
    });
    try {
      final updated = await widget.repository.updateLeadOutcome(
        lead: _lead,
        status: status,
        notes: _notesController.text,
      );
      if (!mounted) return;
      widget.onUpdated(updated);
      setState(() {
        _lead = updated;
        _status = updated.outcomeStatus;
        _notesController.text = updated.outcomeNotes ?? '';
        _success = 'Lead update saved.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  Future<void> _callLead() async {
    final phone = _text(_lead.mobilePhone);
    if (phone == null) return;

    try {
      final opened = await launchUrl(
        Uri(scheme: 'tel', path: phone),
        mode: LaunchMode.externalApplication,
      );
      if (opened || !mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Unable to open the phone dialer.')),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Unable to open the phone dialer.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: EdgeInsets.fromLTRB(
        20,
        4,
        20,
        24 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      children: [
        Center(
          child: Container(
            width: 42,
            height: 4,
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: context.appOutline,
              borderRadius: BorderRadius.circular(999),
            ),
          ),
        ),
        _LeadHero(
          lead: _lead,
          locked: !_canUpdate,
          statusLabel: _statuses[_status] ?? 'New Lead',
          statusColor: _outcomeColor(_status),
          onClose: () => Navigator.of(context).pop(),
        ),
        const SizedBox(height: 14),
        if (!_canUpdate)
          const _Notice(
            icon: Icons.lock_outline,
            message:
                'Contact details and status updates become available after this lead is delivered.',
          )
        else ...[
          _ContactSection(
            phone: _lead.mobilePhone,
            preferredFollowUp: _lead.preferredFollowUpMethod,
            bestTimeToReach: _lead.bestTimeToReach,
            onCall: _callLead,
          ),
          const SizedBox(height: 12),
          _LeadSnapshot(lead: _lead),
          const SizedBox(height: 12),
          _DetailsSection(
            title: 'Financial profile',
            icon: Icons.insights_rounded,
            accent: const Color(0xFF7964D9),
            rows: [
              _DetailValue(
                'Investable assets',
                _lead.assets,
                Icons.account_balance_wallet_outlined,
              ),
              _DetailValue(
                'Retirement savings',
                _lead.retirementSavingsRange,
                Icons.savings_outlined,
              ),
              _DetailValue(
                'Household income',
                _lead.annualHouseholdIncomeRange,
                Icons.payments_outlined,
              ),
              _DetailValue(
                'Expected income source',
                _lead.expectedRetirementIncomeSource,
                Icons.account_balance_outlined,
              ),
              _DetailValue(
                'Monthly savings',
                _lead.monthlySavingsRange,
                Icons.calendar_month_outlined,
              ),
              _DetailValue(
                'Investment comfort',
                _lead.investmentComfortLevel,
                Icons.speed_rounded,
              ),
            ],
          ),
          const SizedBox(height: 12),
          _DetailsSection(
            title: 'Goals & preferences',
            icon: Icons.route_outlined,
            accent: const Color(0xFF0F9F82),
            rows: [
              _DetailValue(
                'Primary interest',
                _lead.activity,
                Icons.star_outline_rounded,
                fullWidth: true,
              ),
              _DetailValue(
                'Retirement timeline',
                _lead.retirementTimeline,
                Icons.timelapse_rounded,
              ),
              _DetailValue(
                'Planning to relocate',
                _lead.planningToRelocateRetirement,
                Icons.location_city_outlined,
              ),
              _DetailValue(
                'Investment goals',
                _lead.mainPurposeForInvesting.join(', '),
                Icons.flag_outlined,
                fullWidth: true,
              ),
              _DetailValue(
                'Current strategies',
                _lead.currentInvestmentStrategies.join(', '),
                Icons.auto_graph_rounded,
                fullWidth: true,
              ),
              _DetailValue(
                'Has financial advisor',
                _lead.hasFinancialAdvisor,
                Icons.support_agent_outlined,
              ),
              _DetailValue(
                'Owns annuity',
                _lead.ownsAnnuity,
                Icons.verified_outlined,
              ),
              _DetailValue(
                'Additional notes',
                _lead.additionalNotes,
                Icons.notes_rounded,
                fullWidth: true,
              ),
            ],
          ),
          const SizedBox(height: 14),
          _LeadUpdatePanel(
            statuses: _statuses,
            status: _status,
            notesController: _notesController,
            saving: _saving,
            error: _error,
            success: _success,
            onStatusChanged: (value) {
              setState(() {
                _status = value;
                _success = null;
              });
            },
            onSave: _status == null ? null : _save,
          ),
        ],
      ],
    );
  }
}

class _LeadHero extends StatelessWidget {
  const _LeadHero({
    required this.lead,
    required this.locked,
    required this.statusLabel,
    required this.statusColor,
    required this.onClose,
  });

  final AdvisorLead lead;
  final bool locked;
  final String statusLabel;
  final Color statusColor;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: context.isDarkMode
              ? const [Color(0xFF17202B), Color(0xFF102629)]
              : const [Color(0xFFF2F7FF), Color(0xFFE9FBF9)],
        ),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: context.appOutline),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Lead Details',
                  style: TextStyle(
                    color: context.appMuted,
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 1.2,
                  ),
                ),
              ),
              Material(
                color: context.appSurface.withValues(alpha: .7),
                shape: const CircleBorder(),
                child: IconButton(
                  onPressed: onClose,
                  tooltip: 'Close lead details',
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.close_rounded, size: 19),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Container(
                width: 54,
                height: 54,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [statusColor, const Color(0xFF27B7CE)],
                  ),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: statusColor.withValues(alpha: .25),
                      blurRadius: 12,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                alignment: Alignment.center,
                child: Text(
                  _leadInitials(lead),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      locked ? 'Locked Lead' : lead.displayName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: context.appInk,
                        fontSize: 22,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -.4,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${lead.stateCode}${_text(lead.zipCode) == null ? '' : '  •  ${lead.zipCode}'}${lead.receivedAt == null ? '' : '  •  ${_leadAge(lead.receivedAt)}'}',
                      style: TextStyle(color: context.appMuted, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              _HeroPill(
                icon: Icons.circle,
                label: statusLabel,
                color: statusColor,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  lead.activity ?? lead.assets ?? 'Lead profile ready',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.end,
                  style: TextStyle(
                    color: context.appMuted,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
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

class _HeroPill extends StatelessWidget {
  const _HeroPill({
    required this.icon,
    required this.label,
    required this.color,
  });

  final IconData icon;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: .24)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 8),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _ContactSection extends StatelessWidget {
  const _ContactSection({
    required this.phone,
    required this.preferredFollowUp,
    required this.bestTimeToReach,
    required this.onCall,
  });

  final String? phone;
  final String? preferredFollowUp;
  final String? bestTimeToReach;
  final VoidCallback onCall;

  @override
  Widget build(BuildContext context) {
    final phoneNumber = _text(phone);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appSurface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: const Color(0xFF1687C8).withValues(alpha: .12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.contact_phone_outlined,
                  color: Color(0xFF1687C8),
                  size: 21,
                ),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Contact this lead',
                      style: TextStyle(
                        color: context.appInk,
                        fontSize: 16,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      'Reach out while their interest is fresh.',
                      style: TextStyle(color: context.appMuted, fontSize: 11),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (phoneNumber != null) ...[
            const SizedBox(height: 14),
            Material(
              color: const Color(0xFF1687C8).withValues(alpha: .08),
              borderRadius: BorderRadius.circular(15),
              child: InkWell(
                key: const Key('lead-phone-link'),
                onTap: onCall,
                borderRadius: BorderRadius.circular(15),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(13, 11, 9, 11),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.phone_in_talk_rounded,
                        color: Color(0xFF1687C8),
                        size: 22,
                      ),
                      const SizedBox(width: 11),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'PHONE NUMBER',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: context.appMuted,
                                fontSize: 9,
                                fontWeight: FontWeight.w900,
                                letterSpacing: .7,
                              ),
                            ),
                            const SizedBox(height: 2),
                            FittedBox(
                              fit: BoxFit.scaleDown,
                              alignment: Alignment.centerLeft,
                              child: Text(
                                phoneNumber,
                                maxLines: 1,
                                softWrap: false,
                                style: const TextStyle(
                                  color: Color(0xFF1687C8),
                                  fontSize: 17,
                                  fontWeight: FontWeight.w900,
                                  decoration: TextDecoration.underline,
                                  decorationColor: Color(0xFF1687C8),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 10),
                      SizedBox(
                        width: 76,
                        height: 40,
                        child: FilledButton.icon(
                          onPressed: onCall,
                          style: FilledButton.styleFrom(
                            backgroundColor: const Color(0xFF1687C8),
                            minimumSize: Size.zero,
                            maximumSize: const Size(76, 40),
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            visualDensity: VisualDensity.compact,
                            padding: const EdgeInsets.symmetric(horizontal: 9),
                          ),
                          icon: const Icon(Icons.call_rounded, size: 16),
                          label: const Text(
                            'Call',
                            style: TextStyle(fontSize: 12),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
          if (_text(preferredFollowUp) != null ||
              _text(bestTimeToReach) != null) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                if (_text(preferredFollowUp) != null)
                  Expanded(
                    child: _ContactMeta(
                      icon: Icons.forum_outlined,
                      label: 'Preferred',
                      value: preferredFollowUp!,
                    ),
                  ),
                if (_text(preferredFollowUp) != null &&
                    _text(bestTimeToReach) != null)
                  const SizedBox(width: 8),
                if (_text(bestTimeToReach) != null)
                  Expanded(
                    child: _ContactMeta(
                      icon: Icons.schedule_rounded,
                      label: 'Best time',
                      value: bestTimeToReach!,
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _ContactMeta extends StatelessWidget {
  const _ContactMeta({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
      decoration: BoxDecoration(
        color: context.appSoftFill,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(icon, color: context.appMuted, size: 17),
          const SizedBox(width: 7),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(color: context.appMuted, fontSize: 9.5),
                ),
                Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: context.appInk,
                    fontSize: 11.5,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LeadSnapshot extends StatelessWidget {
  const _LeadSnapshot({required this.lead});

  final AdvisorLead lead;

  @override
  Widget build(BuildContext context) {
    final items = <({IconData icon, String label, String? value, Color color})>[
      (
        icon: Icons.account_balance_wallet_outlined,
        label: 'Assets',
        value: lead.assets,
        color: const Color(0xFF0F9F82),
      ),
      (
        icon: Icons.timelapse_rounded,
        label: 'Timeline',
        value: lead.retirementTimeline,
        color: const Color(0xFFF59E0B),
      ),
      (
        icon: Icons.star_outline_rounded,
        label: 'Primary interest',
        value: lead.activity,
        color: const Color(0xFF7964D9),
      ),
    ].where((item) => _text(item.value) != null).toList();

    if (items.isEmpty) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appSurface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'LEAD SNAPSHOT',
            style: TextStyle(
              color: context.appMuted,
              fontSize: 10,
              fontWeight: FontWeight.w900,
              letterSpacing: .9,
            ),
          ),
          const SizedBox(height: 11),
          for (var index = 0; index < items.length; index++) ...[
            _SnapshotRow(
              icon: items[index].icon,
              label: items[index].label,
              value: items[index].value!,
              color: items[index].color,
            ),
            if (index != items.length - 1)
              Divider(height: 17, color: context.appOutline),
          ],
        ],
      ),
    );
  }
}

class _SnapshotRow extends StatelessWidget {
  const _SnapshotRow({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 31,
          height: 31,
          decoration: BoxDecoration(
            color: color.withValues(alpha: .11),
            borderRadius: BorderRadius.circular(9),
          ),
          child: Icon(icon, color: color, size: 17),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            label,
            style: TextStyle(color: context.appMuted, fontSize: 11),
          ),
        ),
        const SizedBox(width: 10),
        Flexible(
          flex: 2,
          child: Text(
            value,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.end,
            style: TextStyle(
              color: context.appInk,
              fontSize: 12.5,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
      ],
    );
  }
}

class _LeadUpdatePanel extends StatelessWidget {
  const _LeadUpdatePanel({
    required this.statuses,
    required this.status,
    required this.notesController,
    required this.saving,
    required this.error,
    required this.success,
    required this.onStatusChanged,
    required this.onSave,
  });

  final Map<String, String> statuses;
  final String? status;
  final TextEditingController notesController;
  final bool saving;
  final String? error;
  final String? success;
  final ValueChanged<String?> onStatusChanged;
  final VoidCallback? onSave;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appSurface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: const Color(0xFF18A0B8).withValues(alpha: .11),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: const Icon(
                  Icons.task_alt_rounded,
                  color: Color(0xFF18A0B8),
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Update Status',
                      style: TextStyle(
                        color: context.appInk,
                        fontSize: 17,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      'Record the next milestone and follow-up notes.',
                      style: TextStyle(color: context.appMuted, fontSize: 11),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: status,
            decoration: const InputDecoration(
              labelText: 'Lead status',
              prefixIcon: Icon(Icons.flag_outlined),
            ),
            hint: const Text('Select status'),
            items: statuses.entries
                .map(
                  (entry) => DropdownMenuItem(
                    value: entry.key,
                    child: Text(entry.value),
                  ),
                )
                .toList(),
            onChanged: saving ? null : onStatusChanged,
          ),
          const SizedBox(height: 11),
          TextField(
            controller: notesController,
            enabled: !saving,
            minLines: 3,
            maxLines: 6,
            maxLength: 2000,
            decoration: const InputDecoration(
              labelText: 'Notes',
              hintText: 'Add call notes, appointment time, or objections.',
              alignLabelWithHint: true,
              prefixIcon: Padding(
                padding: EdgeInsets.only(bottom: 50),
                child: Icon(Icons.edit_note_rounded),
              ),
            ),
          ),
          if (error != null) ...[
            const SizedBox(height: 6),
            Text(error!, style: const TextStyle(color: Color(0xFFB91C1C))),
          ],
          if (success != null) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                const Icon(
                  Icons.check_circle_rounded,
                  color: Color(0xFF15803D),
                  size: 18,
                ),
                const SizedBox(width: 7),
                Text(
                  success!,
                  style: const TextStyle(
                    color: Color(0xFF15803D),
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 11),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: FilledButton.icon(
              onPressed: saving ? null : onSave,
              icon: saving
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.save_outlined),
              label: Text(saving ? 'Saving…' : 'Save lead update'),
            ),
          ),
        ],
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF7E6),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFF4D38A)),
      ),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFFB45309)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: Color(0xFF7C4A03)),
            ),
          ),
        ],
      ),
    );
  }
}

class _DetailsSection extends StatelessWidget {
  const _DetailsSection({
    required this.title,
    required this.icon,
    required this.accent,
    required this.rows,
  });

  final String title;
  final IconData icon;
  final Color accent;
  final List<_DetailValue> rows;

  @override
  Widget build(BuildContext context) {
    final visibleRows = rows.where((row) => _text(row.value) != null).toList();
    if (visibleRows.isEmpty) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appSurface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: .11),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: accent, size: 19),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: context.appInk,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, constraints) {
              final itemWidth = (constraints.maxWidth - 8) / 2;
              return Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final row in visibleRows)
                    Container(
                      width: row.fullWidth ? constraints.maxWidth : itemWidth,
                      constraints: const BoxConstraints(minHeight: 76),
                      padding: const EdgeInsets.all(11),
                      decoration: BoxDecoration(
                        color: context.appSoftFill,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: accent.withValues(alpha: .12),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(row.icon, color: accent, size: 15),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  row.label.toUpperCase(),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    color: context.appMuted,
                                    fontSize: 9.5,
                                    fontWeight: FontWeight.w800,
                                    letterSpacing: .5,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 7),
                          Text(
                            row.value!.trim(),
                            maxLines: row.fullWidth ? 4 : 3,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: context.appInk,
                              fontSize: 12.5,
                              height: 1.25,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _DetailValue {
  const _DetailValue(
    this.label,
    this.value,
    this.icon, {
    this.fullWidth = false,
  });

  final String label;
  final String? value;
  final IconData icon;
  final bool fullWidth;
}

String? _text(String? value) {
  final clean = value?.trim();
  return clean == null || clean.isEmpty ? null : clean;
}

Color _outcomeColor(String? value) => switch (value) {
  'contacted' => const Color(0xFFF59E0B),
  'appointment_set' => const Color(0xFF7C3AED),
  'closed_deal' => const Color(0xFF059669),
  _ => const Color(0xFF18A0B8),
};

String _leadInitials(AdvisorLead lead) {
  final first = (lead.firstName ?? '').trim();
  final last = (lead.lastName ?? '').trim();
  if (first.isNotEmpty || last.isNotEmpty) {
    return [
      if (first.isNotEmpty) first.substring(0, 1),
      if (last.isNotEmpty) last.substring(0, 1),
    ].join().toUpperCase();
  }
  return lead.stateCode.length >= 2
      ? lead.stateCode.substring(0, 2).toUpperCase()
      : 'LD';
}

String _leadAge(DateTime? receivedAt) {
  if (receivedAt == null) return 'Just now';
  final difference = DateTime.now().difference(receivedAt);
  if (difference.inMinutes < 60) return '${difference.inMinutes}m ago';
  if (difference.inHours < 24) return '${difference.inHours}h ago';
  return '${difference.inDays}d ago';
}
