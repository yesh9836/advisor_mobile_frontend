import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/screens/advisor/billing_history_sheet.dart';
import 'package:flutter_frontend/screens/advisor/change_password_sheet.dart';
import 'package:flutter_frontend/screens/advisor/license_upload_sheet.dart';
import 'package:flutter_frontend/screens/advisor/notification_preferences_sheet.dart';
import 'package:flutter_frontend/screens/auth/login_screen.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:flutter_frontend/theme/app_theme_controller.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    this.authRepository,
    this.advisorRepository,
    this.documentPicker,
  });

  final AuthRepository? authRepository;
  final AdvisorRepository? advisorRepository;
  final LicenseDocumentPicker? documentPicker;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final AuthRepository _authRepository =
      widget.authRepository ?? AuthRepository();
  late final AdvisorRepository _advisorRepository =
      widget.advisorRepository ?? AdvisorRepository();
  late Future<_ProfileData> _future = _loadProfile();
  bool _isLoggingOut = false;

  Future<_ProfileData> _loadProfile() async {
    final user = await _authRepository.getCurrentUser();
    final licenses = await _authRepository.getMyLicenses();

    return _ProfileData(user: user, licenses: licenses);
  }

  Future<void> _logout() async {
    setState(() => _isLoggingOut = true);
    try {
      await _authRepository.logout();
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const LoginScreen()),
        (route) => false,
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Logout failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _isLoggingOut = false);
    }
  }

  void _refreshProfile() {
    setState(() {
      _future = _loadProfile();
    });
  }

  Future<void> _openLicenseUpload() {
    return showLicenseUploadSheet(
      context: context,
      repository: _authRepository,
      documentPicker: widget.documentPicker,
      onSubmitted: (_) => _refreshProfile(),
    );
  }

  Future<void> _openBillingHistory() {
    return showBillingHistorySheet(
      context: context,
      repository: _advisorRepository,
    );
  }

  Future<void> _openChangePassword() {
    return showChangePasswordSheet(
      context: context,
      repository: _authRepository,
    );
  }

  Future<void> _openNotificationPreferences() {
    return showNotificationPreferencesSheet(
      context: context,
      repository: _advisorRepository,
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_ProfileData>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _Panel(
                child: Text(
                  snapshot.error.toString(),
                  style: TextStyle(color: context.appMuted),
                ),
              ),
            ],
          );
        }

        final data = snapshot.data!;
        return ListView(
          padding: const EdgeInsets.fromLTRB(14, 10, 14, 18),
          children: [
            _ProfileHeader(user: data.user, licenses: data.licenses),
            const SizedBox(height: 9),
            _ContactInfo(user: data.user),
            const SizedBox(height: 9),
            _LicensedStates(licenses: data.licenses, onAdd: _openLicenseUpload),
            const SizedBox(height: 9),
            _AccountActions(
              onBillingHistory: _openBillingHistory,
              onChangePassword: _openChangePassword,
              onNotificationPreferences: _openNotificationPreferences,
            ),
            const SizedBox(height: 9),
            _SignOutButton(isLoading: _isLoggingOut, onTap: _logout),
          ],
        );
      },
    );
  }
}

class _ProfileData {
  _ProfileData({required this.user, required this.licenses});

  final UserProfile user;
  final List<AdvisorLicense> licenses;
}

class _ProfileHeader extends StatelessWidget {
  const _ProfileHeader({required this.user, required this.licenses});

  final UserProfile user;
  final List<AdvisorLicense> licenses;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          children: [
            Container(
              width: 50,
              height: 50,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF252D6D), Color(0xFF27B7CE)],
                ),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Text(
                _initials(user.name),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    licenses.any(
                          (license) => license.verificationStatus == 'verified',
                        )
                        ? 'LICENSED ADVISOR'
                        : 'MY PROFILE',
                    style: const TextStyle(
                      color: AppColors.cyan,
                      fontSize: 9,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1.15,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    user.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: context.appInk,
                      fontSize: 20,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.4,
                    ),
                  ),
                  Text(
                    user.email,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: context.appMuted, fontSize: 11.5),
                  ),
                ],
              ),
            ),
            const AppThemeToggleButton(),
          ],
        ),
        const SizedBox(height: 10),
        Container(
          height: 2,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(99),
            gradient: const LinearGradient(
              colors: [AppColors.cyan, Color(0x3327B7CE), Colors.transparent],
              stops: [0, 0.35, 1],
            ),
          ),
        ),
      ],
    );
  }
}

class _ContactInfo extends StatelessWidget {
  const _ContactInfo({required this.user});

  final UserProfile user;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('Contact Info'),
          const SizedBox(height: 7),
          _InfoRow(label: 'Phone', value: _formatPhone(user.phone)),
          const _DividerLine(),
          _InfoRow(label: 'Email', value: user.email),
          const _DividerLine(),
          const _InfoRow(label: 'Firm', value: 'Advisor Practice'),
        ],
      ),
    );
  }
}

class _LicensedStates extends StatelessWidget {
  const _LicensedStates({required this.licenses, required this.onAdd});

  final List<AdvisorLicense> licenses;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    final visibleLicenses = licenses.isEmpty
        ? <AdvisorLicense>[]
        : licenses.take(5).toList();

    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(child: _SectionTitle('Licensed States')),
              TextButton.icon(
                onPressed: onAdd,
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Add'),
                style: TextButton.styleFrom(
                  foregroundColor: const Color(0xFF18A0B8),
                  backgroundColor: const Color(0xFFE8FBFF),
                  minimumSize: const Size(0, 34),
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(999),
                  ),
                  textStyle: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          if (visibleLicenses.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Text(
                'No licenses submitted yet.',
                style: TextStyle(color: context.appMuted),
              ),
            )
          else
            for (var index = 0; index < visibleLicenses.length; index++) ...[
              _LicenseRow(license: visibleLicenses[index]),
              if (index != visibleLicenses.length - 1) const _DividerLine(),
            ],
        ],
      ),
    );
  }
}

class _LicenseRow extends StatelessWidget {
  const _LicenseRow({required this.license});

  final AdvisorLicense license;

  @override
  Widget build(BuildContext context) {
    final status = _LicenseStatus.fromValue(license.verificationStatus);
    final stateName = _stateName(license.state);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          CircleAvatar(
            radius: 17,
            backgroundColor: status.avatarBackground,
            child: Text(
              license.state,
              style: TextStyle(
                color: status.avatarForeground,
                fontWeight: FontWeight.w900,
                fontSize: 12,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  stateName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: context.appInk,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '${license.state} - ${license.licenseNumber}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: context.appMuted,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          _StatusPill(status: status),
        ],
      ),
    );
  }
}

class _AccountActions extends StatelessWidget {
  const _AccountActions({
    required this.onBillingHistory,
    required this.onChangePassword,
    required this.onNotificationPreferences,
  });

  final VoidCallback onBillingHistory;
  final VoidCallback onChangePassword;
  final VoidCallback onNotificationPreferences;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        children: [
          _ActionRow(
            icon: Icons.credit_card_outlined,
            label: 'Billing History',
            onTap: onBillingHistory,
          ),
          const _DividerLine(),
          _ActionRow(
            icon: Icons.shield_outlined,
            label: 'Change Password',
            onTap: onChangePassword,
          ),
          const _DividerLine(),
          _ActionRow(
            icon: Icons.notifications_none,
            label: 'Notification Prefs',
            onTap: onNotificationPreferences,
          ),
        ],
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({required this.icon, required this.label, this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(
          height: 52,
          child: Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: context.appSoftFill,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: context.appInk, size: 19),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    color: context.appInk,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Icon(
                Icons.chevron_right,
                color: onTap == null
                    ? const Color(0xFFC7D7DD)
                    : const Color(0xFF607987),
                size: 22,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SignOutButton extends StatelessWidget {
  const _SignOutButton({required this.isLoading, required this.onTap});

  final bool isLoading;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: isLoading ? null : onTap,
      icon: isLoading
          ? const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.logout, size: 18),
      label: const Text('Sign Out'),
      style: OutlinedButton.styleFrom(
        foregroundColor: const Color(0xFFEF4444),
        minimumSize: const Size.fromHeight(44),
        side: const BorderSide(color: Color(0xFFFF8A8A)),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontWeight: FontWeight.w900),
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: context.appSurface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: child,
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    return Text(
      label.toUpperCase(),
      style: TextStyle(
        color: context.appMuted,
        fontSize: 11,
        fontWeight: FontWeight.w900,
        letterSpacing: 1.2,
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 70,
            child: Text(
              label,
              style: TextStyle(color: context.appMuted, fontSize: 12),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.right,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: context.appInk,
                fontSize: 13,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DividerLine extends StatelessWidget {
  const _DividerLine();

  @override
  Widget build(BuildContext context) {
    return const Divider(height: 1);
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.status});

  final _LicenseStatus status;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: status.badgeBackground,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        status.label,
        style: TextStyle(
          color: status.badgeForeground,
          fontSize: 10,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _LicenseStatus {
  const _LicenseStatus({
    required this.label,
    required this.avatarBackground,
    required this.avatarForeground,
    required this.badgeBackground,
    required this.badgeForeground,
  });

  final String label;
  final Color avatarBackground;
  final Color avatarForeground;
  final Color badgeBackground;
  final Color badgeForeground;

  static _LicenseStatus fromValue(String value) {
    switch (value) {
      case 'verified':
        return const _LicenseStatus(
          label: 'Approved',
          avatarBackground: Color(0xFFD8FBE5),
          avatarForeground: Color(0xFF059669),
          badgeBackground: Color(0xFFD8FBE5),
          badgeForeground: Color(0xFF059669),
        );
      case 'rejected':
        return const _LicenseStatus(
          label: 'Rejected',
          avatarBackground: Color(0xFFFFDADB),
          avatarForeground: Color(0xFFDC2626),
          badgeBackground: Color(0xFFFFE1E1),
          badgeForeground: Color(0xFFDC2626),
        );
      default:
        return const _LicenseStatus(
          label: 'Pending',
          avatarBackground: Color(0xFFFFF1C7),
          avatarForeground: Color(0xFFD97706),
          badgeBackground: Color(0xFFFFF1C7),
          badgeForeground: Color(0xFFD97706),
        );
    }
  }
}

String _initials(String name) {
  final parts = name
      .trim()
      .split(RegExp(r'\s+'))
      .where((part) => part.isNotEmpty)
      .toList();
  if (parts.isEmpty) return 'AD';
  if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
  return '${parts.first.substring(0, 1)}${parts.last.substring(0, 1)}'
      .toUpperCase();
}

String _formatPhone(String? phone) {
  final value = (phone ?? '').trim();
  if (value.isEmpty) return 'Not added';
  if (value.startsWith('+1') && value.length == 12) {
    return '(${value.substring(2, 5)}) ${value.substring(5, 8)}-${value.substring(8)}';
  }
  return value;
}

String _stateName(String code) {
  const names = {
    'AL': 'Alabama',
    'AK': 'Alaska',
    'AZ': 'Arizona',
    'AR': 'Arkansas',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DE': 'Delaware',
    'FL': 'Florida',
    'GA': 'Georgia',
    'HI': 'Hawaii',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'IA': 'Iowa',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'ME': 'Maine',
    'MD': 'Maryland',
    'MA': 'Massachusetts',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MS': 'Mississippi',
    'MO': 'Missouri',
    'MT': 'Montana',
    'NE': 'Nebraska',
    'NV': 'Nevada',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NY': 'New York',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PA': 'Pennsylvania',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VT': 'Vermont',
    'VA': 'Virginia',
    'WA': 'Washington',
    'WV': 'West Virginia',
    'WI': 'Wisconsin',
    'WY': 'Wyoming',
  };
  return names[code] ?? code;
}
