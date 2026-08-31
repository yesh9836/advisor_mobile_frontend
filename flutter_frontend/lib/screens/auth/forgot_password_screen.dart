import 'package:flutter/material.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:flutter_frontend/theme/app_theme_controller.dart';

class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({
    super.key,
    this.authRepository,
    this.initialEmail = '',
  });

  final AuthRepository? authRepository;
  final String initialEmail;

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  late final AuthRepository _authRepository =
      widget.authRepository ?? AuthRepository();
  late final TextEditingController _emailController = TextEditingController(
    text: widget.initialEmail,
  );
  bool _submitting = false;
  String? _success;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _submitting = true;
      _success = null;
      _error = null;
    });

    try {
      final message = await _authRepository.requestPasswordReset(
        _emailController.text,
      );
      if (!mounted) return;
      setState(() => _success = message);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error is AuthException
            ? error.message
            : 'Unable to process password reset right now.';
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String? _validateEmail(String? value) {
    final email = (value ?? '').trim();
    if (email.isEmpty) return 'Email is required';
    if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(email)) {
      return 'Enter a valid email';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appCanvas,
      appBar: AppBar(
        leading: const BackButton(),
        actions: const [AppThemeToggleButton(), SizedBox(width: 16)],
        title: const Text(
          'Forgot Password',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          height: 56,
                          width: 56,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: context.isDarkMode
                                ? const Color(0xFF12333E)
                                : const Color(0xFFE8F8FC),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: const Icon(
                            Icons.lock_reset_rounded,
                            color: Color(0xFF0087B7),
                            size: 30,
                          ),
                        ),
                        const SizedBox(height: 20),
                        Text(
                          'Reset your password',
                          style: TextStyle(
                            color: context.appInk,
                            fontSize: 22,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Enter your account email and we’ll send password reset instructions if the account exists.',
                          style: TextStyle(
                            color: context.appMuted,
                            height: 1.4,
                          ),
                        ),
                        const SizedBox(height: 24),
                        Text(
                          'EMAIL ADDRESS',
                          style: TextStyle(
                            color: context.appMuted,
                            fontSize: 11,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 1.1,
                          ),
                        ),
                        const SizedBox(height: 8),
                        TextFormField(
                          controller: _emailController,
                          enabled: !_submitting,
                          autofocus: widget.initialEmail.isEmpty,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.done,
                          autocorrect: false,
                          validator: _validateEmail,
                          onFieldSubmitted: (_) =>
                              _submitting ? null : _submit(),
                          decoration: const InputDecoration(
                            hintText: 'alex@wealthadvisors.com',
                            prefixIcon: Icon(Icons.email_outlined),
                          ),
                        ),
                        if (_success != null) ...[
                          const SizedBox(height: 16),
                          _MessagePanel(
                            message: _success!,
                            icon: Icons.check_circle_outline,
                            backgroundColor: Color(0xFFECFDF5),
                            borderColor: Color(0xFFA7F3D0),
                            foregroundColor: Color(0xFF047857),
                          ),
                        ],
                        if (_error != null) ...[
                          const SizedBox(height: 16),
                          _MessagePanel(
                            message: _error!,
                            icon: Icons.error_outline,
                            backgroundColor: Color(0xFFFFF1F2),
                            borderColor: Color(0xFFFECACA),
                            foregroundColor: Color(0xFF9F1239),
                          ),
                        ],
                        const SizedBox(height: 20),
                        FilledButton(
                          onPressed: _submitting ? null : _submit,
                          child: _submitting
                              ? const SizedBox.square(
                                  dimension: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                )
                              : const Text('Send reset instructions'),
                        ),
                        const SizedBox(height: 8),
                        TextButton.icon(
                          onPressed: _submitting
                              ? null
                              : () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.arrow_back, size: 18),
                          label: const Text('Back to sign in'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _MessagePanel extends StatelessWidget {
  const _MessagePanel({
    required this.message,
    required this.icon,
    required this.backgroundColor,
    required this.borderColor,
    required this.foregroundColor,
  });

  final String message;
  final IconData icon;
  final Color backgroundColor;
  final Color borderColor;
  final Color foregroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: foregroundColor, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: foregroundColor, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}
