import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/theme/app_theme.dart';

Future<void> showNotificationPreferencesSheet({
  required BuildContext context,
  required AdvisorRepository repository,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).bottomSheetTheme.backgroundColor,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (_) => NotificationPreferencesSheet(repository: repository),
  );
}

class NotificationPreferencesSheet extends StatefulWidget {
  const NotificationPreferencesSheet({super.key, required this.repository});

  final AdvisorRepository repository;

  @override
  State<NotificationPreferencesSheet> createState() =>
      _NotificationPreferencesSheetState();
}

class _NotificationPreferencesSheetState
    extends State<NotificationPreferencesSheet> {
  DeliverySettings? _settings;
  bool _emailEnabled = false;
  bool _smsEnabled = false;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final settings = await widget.repository.getDeliverySettings();
      if (!mounted) return;
      setState(() {
        _settings = settings;
        _emailEnabled = settings.emailAlertsEnabled;
        _smsEnabled = settings.smsAlertsEnabled;
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    final settings = _settings;
    if (_saving || settings == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.repository.updateDeliverySettings(
        emailAlertsEnabled: _emailEnabled,
        smsAlertsEnabled: _smsEnabled,
        expectedVersion: settings.version,
      );
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Notification preferences saved.')),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        20,
        18,
        20,
        24 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Notification Preferences',
            style: TextStyle(
              color: context.appInk,
              fontSize: 21,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Choose how you want to be alerted when new leads are delivered.',
            style: TextStyle(color: context.appMuted, height: 1.35),
          ),
          const SizedBox(height: 18),
          if (_loading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(28),
                child: CircularProgressIndicator(),
              ),
            )
          else if (_settings == null)
            Center(
              child: Column(
                children: [
                  Text(
                    _error ?? 'Unable to load notification preferences.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Color(0xFFB91C1C)),
                  ),
                  const SizedBox(height: 8),
                  TextButton(onPressed: _load, child: const Text('Try again')),
                ],
              ),
            )
          else ...[
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              secondary: const Icon(
                Icons.mail_outline,
                color: Color(0xFF18A0B8),
              ),
              title: const Text('Email alerts'),
              subtitle: const Text('Receive lead delivery updates by email.'),
              value: _emailEnabled,
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _emailEnabled = value),
            ),
            const Divider(),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              secondary: const Icon(
                Icons.sms_outlined,
                color: Color(0xFF18A0B8),
              ),
              title: const Text('SMS alerts'),
              subtitle: const Text(
                'Receive lead delivery updates by text message.',
              ),
              value: _smsEnabled,
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _smsEnabled = value),
            ),
            if (_settings!.warnings.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                _settings!.warnings.join('\n'),
                style: const TextStyle(color: Color(0xFFB45309)),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 10),
              Text(_error!, style: const TextStyle(color: Color(0xFFB91C1C))),
            ],
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: FilledButton(
                onPressed: _saving ? null : _save,
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF18A0B8),
                ),
                child: Text(_saving ? 'Saving...' : 'Save preferences'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
