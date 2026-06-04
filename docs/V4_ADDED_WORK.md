# V4 added work

V4 moves the prototype further toward a customer self-service and bakery operations platform.

## Customer-facing additions

- Product details dialog with options, allergen badges, lead time, stock policy, and source notes.
- Favorite products for logged-in customers.
- One-click reorder from account order history.
- Order change requests for edits, cancellations, rescheduling, and substitutions.
- Public review submission with admin approval before publishing.
- Published SEO/campaign pages rendered at `/page/<slug>`.
- Delivery and pickup policy cards.
- Customer loyalty point summary in account view.
- Mock password reset request flow that queues a reset notification.

## Admin additions

- Customer console with users, loyalty, favorites, change requests, reviews, and invoices.
- Change request approval workflow.
- Review moderation workflow.
- Invoice creation from orders.
- Bundle builder using JSON product quantities.
- Product recipe/cost links using product and ingredient records.
- Margin report showing rough ingredient cost and gross margin warnings.
- Local event rules and weather adjustment rules for forecasting.
- POS CSV rows are parsed into `pos_sales_rows` instead of only recording an import batch.
- Notification outbox rows can be marked sent.
- Printable pickup labels at `/labels?date=YYYY-MM-DD`.

## Remaining caveats

Ingredient costs and recipe quantities are planning placeholders. Real margins require owner-verified supplier prices and production recipes. Payment, SMS, email, password reset, delivery, and weather integrations are still mocked or manually entered.
