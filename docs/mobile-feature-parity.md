# Advisor web-to-mobile feature parity

This backlog covers advisor-facing functionality. Admin inventory, user review,
orders, imports, analytics, offers, plans, and license review remain web-only by
design because they are operational workflows rather than advisor workflows.

## Completed

1. **Goals funnel** — Mobile Goals now shows Leads → Appointments → Deals →
   Income Goal and lets the advisor edit average commission, lead-to-appointment
   rate, and appointment-to-deal rate.
2. **Billing invoice detail** — Mobile Billing History now shows package,
   amount, payment status, exact local date/time, Stripe invoice reference,
   description, card metadata, an in-app hosted invoice view, and a PDF action.
3. **Lead-notification app link** — New lead-delivery emails use an app-aware
   landing page that opens the mobile Inbox when installed and retains a web
   Inbox fallback.

## Next advisor parity increments

1. **Inbox CSV export and share** — Export the currently filtered lead set and
   open the native share/download sheet.
2. **Credits and purchase fulfillment summary** — Add remaining credits, total
   credits purchased, completed purchases, latest purchase delivery progress,
   and pending auto-delivery counts to Profile.
3. **Home delivery-settings snapshot** — Surface email/SMS alert status and
   current target states on Home with a direct edit action.
4. **Goals plan controls** — Add explicit current target-year/annual-plan review
   without allowing future activity to appear as actual history.
5. **Invoice empty/degraded states** — Explain when Stripe has no invoice yet
   and distinguish invoice retrieval failures from local purchase-history
   fallback records.
6. **Password reset handoff** — Open password-reset email links in the mobile
   app when installed, with the existing secure web flow as fallback.

## Platform-specific behavior retained

- Web uses paginated lead tables; mobile uses infinite scrolling.
- Admin routes remain in the web portal only.
- Stripe-hosted Checkout remains an in-app secure browser surface rather than a
  custom card form, preserving Stripe-hosted payment handling.
