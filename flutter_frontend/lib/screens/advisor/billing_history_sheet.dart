import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';
import 'package:flutter_frontend/theme/app_theme.dart';
import 'package:url_launcher/url_launcher.dart';

typedef BillingUrlLauncher = Future<bool> Function(Uri uri, bool inApp);

Future<bool> _launchBillingUrl(Uri uri, bool inApp) => launchUrl(
  uri,
  mode: inApp ? LaunchMode.inAppBrowserView : LaunchMode.externalApplication,
);

Future<void> showBillingHistorySheet({
  required BuildContext context,
  required AdvisorRepository repository,
  BillingUrlLauncher launcher = _launchBillingUrl,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => FractionallySizedBox(
      heightFactor: 0.88,
      child: BillingHistorySheet(repository: repository, launcher: launcher),
    ),
  );
}

class BillingHistorySheet extends StatefulWidget {
  const BillingHistorySheet({
    super.key,
    required this.repository,
    this.launcher = _launchBillingUrl,
  });

  final AdvisorRepository repository;
  final BillingUrlLauncher launcher;

  @override
  State<BillingHistorySheet> createState() => _BillingHistorySheetState();
}

class _BillingHistorySheetState extends State<BillingHistorySheet> {
  late Future<BillingHistoryData> _future = widget.repository
      .getBillingHistory();

  void _retry() {
    setState(() {
      _future = widget.repository.getBillingHistory();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<BillingHistoryData>(
      future: _future,
      builder: (context, snapshot) {
        return ListView(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Billing History',
                        style: TextStyle(
                          color: context.appInk,
                          fontSize: 24,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      Text(
                        'Invoices and purchase history.',
                        style: TextStyle(color: context.appMuted),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  tooltip: 'Close billing history',
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            const SizedBox(height: 18),
            if (snapshot.connectionState == ConnectionState.waiting)
              const Padding(
                padding: EdgeInsets.only(top: 60),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (snapshot.hasError)
              _BillingNotice(
                icon: Icons.error_outline,
                message: snapshot.error.toString(),
                actionLabel: 'Retry',
                onAction: _retry,
              )
            else ...[
              if (snapshot.data!.providerStatus != 'healthy') ...[
                const _BillingNotice(
                  icon: Icons.info_outline,
                  message:
                      'Live Stripe billing details are temporarily unavailable. Showing purchase history.',
                ),
                const SizedBox(height: 12),
              ],
              if (snapshot.data!.paymentMethod case final paymentMethod?) ...[
                _PaymentMethodCard(paymentMethod: paymentMethod),
                const SizedBox(height: 16),
              ],
              Text(
                'Recent Purchases',
                style: TextStyle(
                  color: context.appInk,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 10),
              if (snapshot.data!.invoices.isEmpty)
                const _BillingNotice(
                  icon: Icons.receipt_long_outlined,
                  message: 'No invoices or purchases yet.',
                )
              else
                for (final invoice in snapshot.data!.invoices)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _InvoiceCard(
                      invoice: invoice,
                      launcher: widget.launcher,
                    ),
                  ),
            ],
          ],
        );
      },
    );
  }
}

class _PaymentMethodCard extends StatelessWidget {
  const _PaymentMethodCard({required this.paymentMethod});

  final BillingPaymentMethod paymentMethod;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF202860),
        borderRadius: BorderRadius.circular(16),
        boxShadow: context.appCardShadows,
      ),
      child: Row(
        children: [
          const Icon(Icons.credit_card, color: Colors.white, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${paymentMethod.brand.toUpperCase()} •••• ${paymentMethod.last4}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  [
                    'Expires ${paymentMethod.expMonth.toString().padLeft(2, '0')}/${paymentMethod.expYear}',
                    if (paymentMethod.funding?.trim().isNotEmpty ?? false)
                      _titleCase(paymentMethod.funding!),
                    if (paymentMethod.country?.trim().isNotEmpty ?? false)
                      paymentMethod.country!.toUpperCase(),
                  ].join('  •  '),
                  style: const TextStyle(color: Color(0xFFD6E6EF)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _InvoiceCard extends StatelessWidget {
  const _InvoiceCard({required this.invoice, required this.launcher});

  final BillingInvoice invoice;
  final BillingUrlLauncher launcher;

  Future<void> _open(
    BuildContext context,
    String rawUrl, {
    required bool inApp,
  }) async {
    final uri = Uri.tryParse(rawUrl);
    final opened = uri != null && await launcher(uri, inApp);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Unable to open this invoice.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final completed =
        invoice.status.toLowerCase() == 'paid' ||
        invoice.status.toLowerCase() == 'completed';
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: context.appSurfaceRaised,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                backgroundColor: completed
                    ? const Color(0xFFD8FBE5)
                    : const Color(0xFFFFF1C7),
                child: Icon(
                  Icons.receipt_long_outlined,
                  color: completed
                      ? const Color(0xFF059669)
                      : const Color(0xFFD97706),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      invoice.packageName?.trim().isNotEmpty ?? false
                          ? invoice.packageName!.trim()
                          : 'Lead purchase',
                      style: TextStyle(
                        color: context.appInk,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${_formatDate(invoice.createdAt)} · ${_titleCase(invoice.status)}',
                      style: TextStyle(color: context.appMuted, fontSize: 12),
                    ),
                    if (invoice.description?.trim().isNotEmpty ?? false) ...[
                      const SizedBox(height: 4),
                      Text(
                        invoice.description!.trim(),
                        style: TextStyle(color: context.appMuted, fontSize: 12),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                _formatAmount(invoice.amountPaidCents, invoice.currency),
                style: TextStyle(
                  color: context.appInk,
                  fontWeight: FontWeight.w700,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Invoice ${_shortInvoiceId(invoice.id)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(color: context.appMuted, fontSize: 11),
                ),
              ),
              if (invoice.hostedInvoiceUrl?.trim().isNotEmpty ?? false)
                TextButton.icon(
                  onPressed: () =>
                      _open(context, invoice.hostedInvoiceUrl!, inApp: true),
                  icon: const Icon(Icons.visibility_outlined, size: 17),
                  label: const Text('View'),
                ),
              if (invoice.invoicePdfUrl?.trim().isNotEmpty ?? false)
                TextButton.icon(
                  onPressed: () =>
                      _open(context, invoice.invoicePdfUrl!, inApp: false),
                  icon: const Icon(Icons.download_outlined, size: 17),
                  label: const Text('PDF'),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _BillingNotice extends StatelessWidget {
  const _BillingNotice({
    required this.icon,
    required this.message,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: context.appSoftFill,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: context.appOutline),
        boxShadow: context.appCardShadows,
      ),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF18A0B8)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(message, style: TextStyle(color: context.appMuted)),
          ),
          if (actionLabel != null)
            TextButton(onPressed: onAction, child: Text(actionLabel!)),
        ],
      ),
    );
  }
}

String _formatDate(DateTime value) {
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  final hour = value.hour % 12 == 0 ? 12 : value.hour % 12;
  final minute = value.minute.toString().padLeft(2, '0');
  final period = value.hour < 12 ? 'AM' : 'PM';
  return '${months[value.month - 1]} ${value.day}, ${value.year} at $hour:$minute $period';
}

String _shortInvoiceId(String value) {
  if (value.trim().isEmpty) return 'unavailable';
  return value.length <= 18
      ? value
      : '${value.substring(0, 10)}…${value.substring(value.length - 5)}';
}

String _formatAmount(int cents, String currency) {
  final amount = cents / 100;
  final prefix = currency.toUpperCase() == 'USD'
      ? r'$'
      : '${currency.toUpperCase()} ';
  return '$prefix${amount.toStringAsFixed(amount == amount.roundToDouble() ? 0 : 2)}';
}

String _titleCase(String value) {
  final clean = value.replaceAll('_', ' ').trim();
  if (clean.isEmpty) return 'Unknown';
  return '${clean[0].toUpperCase()}${clean.substring(1).toLowerCase()}';
}
