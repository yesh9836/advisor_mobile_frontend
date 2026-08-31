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
    showDragHandle: true,
    builder: (_) => FractionallySizedBox(
      heightFactor: 0.9,
      child: LeadDetailsSheet(
        lead: lead,
        repository: repository,
        onUpdated: onUpdated,
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
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const CircleAvatar(
              radius: 24,
              backgroundColor: Color(0xFF18A0B8),
              child: Icon(Icons.person_outline, color: Colors.white),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Lead Details',
                    style: TextStyle(color: context.appMuted),
                  ),
                  Text(
                    _canUpdate ? _lead.displayName : 'Locked Lead',
                    style: TextStyle(
                      color: context.appInk,
                      fontSize: 24,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  Text(
                    '${_lead.stateCode}${_text(_lead.zipCode) == null ? '' : ' · ${_lead.zipCode}'}',
                    style: TextStyle(color: context.appMuted),
                  ),
                ],
              ),
            ),
            IconButton(
              onPressed: () => Navigator.of(context).pop(),
              tooltip: 'Close lead details',
              icon: const Icon(Icons.close),
            ),
          ],
        ),
        const SizedBox(height: 18),
        if (!_canUpdate)
          const _Notice(
            icon: Icons.lock_outline,
            message:
                'Contact details and status updates become available after this lead is delivered.',
          )
        else ...[
          _DetailsSection(
            title: 'Contact',
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
          const SizedBox(height: 18),
          Text(
            'Update Status',
            style: TextStyle(
              color: context.appInk,
              fontSize: 18,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _status,
            decoration: const InputDecoration(
              labelText: 'Lead status',
              border: OutlineInputBorder(),
            ),
            hint: const Text('Select status'),
            items: _statuses.entries
                .map(
                  (entry) => DropdownMenuItem(
                    value: entry.key,
                    child: Text(entry.value),
                  ),
                )
                .toList(),
            onChanged: _saving
                ? null
                : (value) {
                    setState(() {
                      _status = value;
                      _success = null;
                    });
                  },
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _notesController,
            enabled: !_saving,
            minLines: 3,
            maxLines: 6,
            maxLength: 2000,
            decoration: const InputDecoration(
              labelText: 'Notes',
              hintText: 'Add call notes, appointment time, or objections.',
              alignLabelWithHint: true,
              border: OutlineInputBorder(),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: Color(0xFFB91C1C))),
          ],
          if (_success != null) ...[
            const SizedBox(height: 8),
            Text(
              _success!,
              style: const TextStyle(
                color: Color(0xFF15803D),
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          const SizedBox(height: 12),
          SizedBox(
            height: 48,
            child: FilledButton.icon(
              onPressed: _saving || _status == null ? null : _save,
              icon: _saving
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.save_outlined),
              label: Text(_saving ? 'Saving…' : 'Save lead update'),
            ),
          ),
        ],
      ],
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
  const _DetailsSection({required this.title, required this.rows});

  final String title;
  final List<_DetailValue> rows;

  @override
  Widget build(BuildContext context) {
    final visibleRows = rows.where((row) => _text(row.value) != null).toList();
    if (visibleRows.isEmpty) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appSoftFill,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
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
          const SizedBox(height: 10),
          for (var index = 0; index < visibleRows.length; index++) ...[
            if (index > 0) const Divider(height: 18),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 120,
                  child: Text(
                    visibleRows[index].label,
                    style: TextStyle(color: context.appMuted),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    visibleRows[index].value!.trim(),
                    style: TextStyle(
                      color: context.appInk,
                      fontWeight: FontWeight.w700,
                    ),
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

class _DetailValue {
  const _DetailValue(this.label, this.value);

  final String label;
  final String? value;
}

String? _text(String? value) {
  final clean = value?.trim();
  return clean == null || clean.isEmpty ? null : clean;
}
