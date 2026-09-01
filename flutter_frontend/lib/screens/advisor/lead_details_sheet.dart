import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/theme/app_theme.dart';

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
          _DetailsSection(
            title: 'Contact',
            icon: Icons.contact_phone_outlined,
            accent: const Color(0xFF1687C8),
            rows: [
              _DetailValue('Phone', _lead.mobilePhone),
              _DetailValue(
                'Preferred follow-up',
                _lead.preferredFollowUpMethod,
              ),
              _DetailValue('Best time to reach', _lead.bestTimeToReach),
            ],
          ),
          const SizedBox(height: 12),
          _DetailsSection(
            title: 'Retirement & finances',
            icon: Icons.insights_rounded,
            accent: const Color(0xFF7964D9),
            rows: [
              _DetailValue('Primary interest', _lead.activity),
              _DetailValue('Retirement timeline', _lead.retirementTimeline),
              _DetailValue('Investable assets', _lead.assets),
              _DetailValue('Retirement savings', _lead.retirementSavingsRange),
              _DetailValue(
                'Household income',
                _lead.annualHouseholdIncomeRange,
              ),
              _DetailValue(
                'Expected income source',
                _lead.expectedRetirementIncomeSource,
              ),
              _DetailValue('Investment comfort', _lead.investmentComfortLevel),
              _DetailValue(
                'Investment goals',
                _lead.mainPurposeForInvesting.join(', '),
              ),
              _DetailValue(
                'Current strategies',
                _lead.currentInvestmentStrategies.join(', '),
              ),
              _DetailValue('Has financial advisor', _lead.hasFinancialAdvisor),
              _DetailValue('Owns annuity', _lead.ownsAnnuity),
              _DetailValue('Additional notes', _lead.additionalNotes),
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
              Text(
                title,
                style: TextStyle(
                  color: context.appInk,
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
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
                      width: itemWidth,
                      constraints: const BoxConstraints(minHeight: 68),
                      padding: const EdgeInsets.all(10),
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
                          Text(
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
                          const SizedBox(height: 5),
                          Text(
                            row.value!.trim(),
                            maxLines: 3,
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
  const _DetailValue(this.label, this.value);

  final String label;
  final String? value;
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
