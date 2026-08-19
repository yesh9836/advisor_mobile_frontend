import 'package:flutter/material.dart';
import 'package:flutter_frontend/models/advisor_models.dart';
import 'package:flutter_frontend/repositories/advisor_repository.dart';

Future<void> showBillingHistorySheet({
  required BuildContext context,
  required AdvisorRepository repository,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => FractionallySizedBox(
      heightFactor: 0.88,
      child: BillingHistorySheet(repository: repository),
    ),
  );
}

class BillingHistorySheet extends StatefulWidget {
  const BillingHistorySheet({super.key, required this.repository});

  final AdvisorRepository repository;

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
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Billing History',
                        style: TextStyle(
                          color: Color(0xFF202860),
                          fontSize: 24,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      Text(
                        'Invoices and purchase history.',
                        style: TextStyle(color: Color(0xFF58707D)),
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
              const Text(
                'Recent Purchases',
                style: TextStyle(
                  color: Color(0xFF202860),
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
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
                    child: _InvoiceCard(invoice: invoice),
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
                    fontWeight: FontWeight.w900,
                  ),
                ),
                Text(
                  'Expires ${paymentMethod.expMonth.toString().padLeft(2, '0')}/${paymentMethod.expYear}',
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
  const _InvoiceCard({required this.invoice});

  final BillingInvoice invoice;

  @override
  Widget build(BuildContext context) {
    final completed =
        invoice.status.toLowerCase() == 'paid' ||
        invoice.status.toLowerCase() == 'completed';
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFCFE4EC)),
      ),
      child: Row(
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
                  style: const TextStyle(
                    color: Color(0xFF202860),
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '${_formatDate(invoice.createdAt)} · ${_titleCase(invoice.status)}',
                  style: const TextStyle(
                    color: Color(0xFF58707D),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            _formatAmount(invoice.amountPaidCents, invoice.currency),
            style: const TextStyle(
              color: Color(0xFF202860),
              fontWeight: FontWeight.w900,
            ),
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
        color: const Color(0xFFF7FBFD),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFCFE4EC)),
      ),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF18A0B8)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: Color(0xFF58707D)),
            ),
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
  return '${months[value.month - 1]} ${value.day}, ${value.year}';
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
