import 'package:flutter/material.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';

Future<void> showChangePasswordSheet({
  required BuildContext context,
  required AuthRepository repository,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: const Color(0xFFF9F7FF),
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (_) => ChangePasswordSheet(repository: repository),
  );
}

class ChangePasswordSheet extends StatefulWidget {
  const ChangePasswordSheet({super.key, required this.repository});

  final AuthRepository repository;

  @override
  State<ChangePasswordSheet> createState() => _ChangePasswordSheetState();
}

class _ChangePasswordSheetState extends State<ChangePasswordSheet> {
  final _formKey = GlobalKey<FormState>();
  final _currentController = TextEditingController();
  final _newController = TextEditingController();
  final _confirmController = TextEditingController();
  bool _saving = false;
  bool _showCurrent = false;
  bool _showNew = false;
  String? _error;

  @override
  void dispose() {
    _currentController.dispose();
    _newController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving || !_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.repository.changePassword(
        currentPassword: _currentController.text,
        newPassword: _newController.text,
      );
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Password changed successfully.')),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(
        20,
        18,
        20,
        24 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Change Password',
              style: TextStyle(
                color: Color(0xFF202860),
                fontSize: 21,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Enter your current password, then choose a new one.',
              style: TextStyle(color: Color(0xFF58707D)),
            ),
            const SizedBox(height: 18),
            TextFormField(
              controller: _currentController,
              obscureText: !_showCurrent,
              textInputAction: TextInputAction.next,
              autofillHints: const [AutofillHints.password],
              decoration: InputDecoration(
                labelText: 'Current password',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  tooltip: _showCurrent ? 'Hide password' : 'Show password',
                  onPressed: () => setState(() => _showCurrent = !_showCurrent),
                  icon: Icon(
                    _showCurrent ? Icons.visibility_off : Icons.visibility,
                  ),
                ),
              ),
              validator: (value) => (value == null || value.isEmpty)
                  ? 'Enter your current password.'
                  : null,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _newController,
              obscureText: !_showNew,
              textInputAction: TextInputAction.next,
              autofillHints: const [AutofillHints.newPassword],
              decoration: InputDecoration(
                labelText: 'New password',
                helperText: 'Use at least 8 characters.',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  tooltip: _showNew ? 'Hide password' : 'Show password',
                  onPressed: () => setState(() => _showNew = !_showNew),
                  icon: Icon(
                    _showNew ? Icons.visibility_off : Icons.visibility,
                  ),
                ),
              ),
              validator: (value) {
                if (value == null || value.length < 8) {
                  return 'New password must be at least 8 characters.';
                }
                if (value == _currentController.text) {
                  return 'Choose a password different from the current one.';
                }
                return null;
              },
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _confirmController,
              obscureText: !_showNew,
              textInputAction: TextInputAction.done,
              autofillHints: const [AutofillHints.newPassword],
              onFieldSubmitted: (_) => _save(),
              decoration: const InputDecoration(
                labelText: 'Confirm new password',
                border: OutlineInputBorder(),
              ),
              validator: (value) => value != _newController.text
                  ? 'Passwords do not match.'
                  : null,
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Color(0xFFB91C1C))),
            ],
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: FilledButton(
                onPressed: _saving ? null : _save,
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF18A0B8),
                ),
                child: Text(_saving ? 'Changing...' : 'Change Password'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
