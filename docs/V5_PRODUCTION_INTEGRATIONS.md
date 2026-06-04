# v5 production integration plan

This build starts solving the remaining launch blockers by adding configurable production adapters, admin controls, and evidence tracking. It still needs real vendor accounts, owner decisions, and live QA before public ordering.

## Payments

Implemented:

- Payment provider setting: `mock`, `stripe`, or `square`.
- Stripe Checkout Session adapter using direct HTTPS API calls.
- Square hosted payment link adapter using direct HTTPS API calls.
- Square webhook endpoint at `/api/webhooks/square` with optional signature validation.
- Payment intent records with provider reference, hosted checkout URL, status, notes, and integration events.
- Stripe webhook endpoint at `/api/webhooks/stripe` that updates payment intent status when provider events arrive.
- Customer checkout now displays a hosted payment link when a deposit or full payment is required.

Required environment variables:

```bash
JB_PUBLIC_BASE_URL=https://order.example.com
JB_PAYMENT_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_live_or_test_value
```

For Square:

```bash
JB_PUBLIC_BASE_URL=https://order.example.com
JB_PAYMENT_PROVIDER=square
SQUARE_ACCESS_TOKEN=EAAA...
SQUARE_LOCATION_ID=LOCATION_ID
SQUARE_ENV=sandbox
SQUARE_WEBHOOK_SIGNATURE_KEY=replace-with-square-signature-key
SQUARE_WEBHOOK_NOTIFICATION_URL=https://order.example.com/api/webhooks/square
```

Next production tasks:

- Configure the owner payment account.
- Test $1 deposits in sandbox.
- Configure provider webhook signing verification before live money.
- Decide whether all cakes require deposit, full payment, or pay-at-pickup.
- Verify tax rules with the bakery accountant.

## SMS and email

Implemented:

- SendGrid transactional email adapter.
- Twilio SMS adapter.
- Notification outbox with provider, provider response, attempts, sent timestamp, and failure state.
- Admin queue processor with dry-run option and live send option.
- Password reset, order ready, staff account, quote, and review-request messages are queued.

Required environment variables:

```bash
SENDGRID_API_KEY=SG...
SENDGRID_FROM_EMAIL=orders@example.com
SENDGRID_FROM_NAME=Juquilita Bakery
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_PHONE=+1423...
```

Next production tasks:

- Verify the sender email domain.
- Verify SMS registration and compliance for the bakery number.
- Decide which messages are bilingual.
- Add delivery status webhooks after the first live pilot.

## Password reset

Implemented:

- Generic reset request response to avoid account enumeration.
- Random reset token.
- HMAC-SHA256 token digest storage.
- Token suffix for troubleshooting without storing the token.
- Expiring token window controlled by `password_reset_token_minutes`.
- Reset confirmation page at `/reset.html`.
- User sessions are revoked after password reset.

## Two-factor admin login

Implemented:

- Authenticator-app TOTP setup.
- Recovery codes stored as hashes.
- Login challenge flow for enabled accounts.
- Optional global staff 2FA enforcement using `admin_2fa_required=true`.
- Audit logs for setup, enable, disable, and login.

Admin steps:

1. Log in as owner/admin.
2. Open Security and staff.
3. Start 2FA setup.
4. Add the Base32 secret or otpauth URI to an authenticator app.
5. Enter the current code to confirm.
6. Store recovery codes offline.
7. Set `admin_2fa_required=true` after all admin users have enabled 2FA.

## Staff roles

Implemented:

- Staff roles: owner, manager, cashier, baker, decorator, wholesale manager.
- Permission catalog.
- Role-permission mapping.
- Direct permission grants.
- Admin route permission checks.
- Staff user creation and update workflow.

Next production tasks:

- Have the owner approve exact permissions.
- Create real staff accounts.
- Remove demo credentials.
- Test each role on a real mobile device and a bakery counter device.

## Product photos, recipes, and supplier costs

Implemented:

- Product photo upload.
- Photo shot list seeded for active products missing verified photos.
- Supplier price quote records.
- Verified supplier quote updates ingredient unit cost.
- Recipe verification records by product and version.
- Margin report uses ingredient-cost links and warns on dangerous margins.

Next production tasks:

- Photograph the actual bakery case and cakes.
- Upload approved photos product by product.
- Enter invoices or supplier price sheets.
- Have the owner verify recipes, yields, and labor minutes.
- Re-run margin report and adjust prices or promos.
