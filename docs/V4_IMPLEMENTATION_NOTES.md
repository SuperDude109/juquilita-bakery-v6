# V4 implementation notes

## Research basis

The catalog and bakery identity are grounded in the uploaded Juquilita source text and public Juquilita website. The app uses source-menu pricing where exact pricing is present and keeps seasonal/custom items quote-based when public pricing varies.

## Implemented from the 100-item backlog

V4 directly implements or scaffolds the highest-impact items:

- Owner verification workflow for every product.
- Master catalog verification table.
- Product photo upload tool and local image storage.
- Richer cake and seasonal quote workflow.
- Deposit and payment-intent scaffolding.
- Receipt generation.
- Notification outbox for email, SMS, and admin alerts.
- Business-hour, slot-capacity, closure, and lead-time enforcement.
- Printable kitchen tickets and production summaries.
- Admin order filters.
- Quote offer and quote-to-order conversion.
- Wholesale approval and standing-order pause/resume.
- Partner consent guardrails.
- Admin audit log viewer.
- Product availability badges and order tracking.
- Store open/closed banner.
- POS import staging.
- Forecast caveat and ingredient estimates.
- Ingredient inventory, supplier list, allergens, SEO pages, content blocks, UAT scenarios, and 100-item launch checklist.

## Implemented as scaffold, not full production

These items are intentionally scaffolded because they require external providers, owner decisions, or production infrastructure:

- Stripe/Square payment processing.
- SMS and email sending.
- Real POS import transformation.
- Weather and local-event integrations.
- Google Business Profile alignment.
- Product label printing.
- Loyalty, abandoned cart recovery, and review automation.
- Password reset and admin two-factor authentication.
- PostgreSQL migration and production framework migration.

## Practical next sprint

1. Upload real product photos.
2. Mark every product as owner verified, needs price check, needs photo, or retired.
3. Enter true sales tax settings after accountant review.
4. Replace demo credentials.
5. Choose Stripe or Square and wire the payment-intent abstraction to real checkout.
6. Connect an email/SMS provider to the notification outbox.
7. Test the UAT scenarios with the owner, cashier, baker, cake decorator, and a wholesale buyer.
