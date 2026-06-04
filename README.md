# Juquilita Bakery v6

A local commerce and bakery-operations prototype for Juquilita Bakery in Morristown, Tennessee.

v6 stabilizes the bakery operating prototype around a stronger storefront, rush-period admin workflow, private receipts, customer substitution preferences, seasonal campaign capacity, product-batch planning, refund records, tax exports, and standing-order run generation. v5 production integrations remain present, including payment adapters, SendGrid/Twilio paths, password reset, 2FA, staff roles, QA tracking, backups, and monitoring scaffolds.

## Run locally

```bash
python3 server.py --init-db
python3 server.py
```

Storefront:

```text
http://127.0.0.1:8000
```

Admin console:

```text
http://127.0.0.1:8000/admin.html
```

## Demo logins

```text
Admin owner: admin@juquilita.local / AdminPass2026!
Premium shop buyer: wholesale@taqueria.local / PanDulce2026!
Guest: guest@juquilita.local / GuestPass2026!
Cashier: cashier@juquilita.local / CashierPass2026!
Baker: baker@juquilita.local / BakerPass2026!
Cake decorator: decorator@juquilita.local / DecoratorPass2026!
```

These are demo-only. Replace them before public deployment.

## Smoke test

```bash
python3 tests/smoke_test.py
```

## Import old website photos

```bash
python3 scripts/import_relabel_images.py
```

The importer uses `/Users/tt/Desktop/juquilita_relabel_output`, copies the SEO-friendly filenames from `renamed_images/` into `public/imported/website/`, writes `manifest.json`, and then applies the canonical product image map. Rebuilding the database with `--init-db` reapplies the manifest and canonical map automatically when those files are present.

Product cards resolve photos from `juquilita_canonical_product_image_map.json` by `canonicalKey`. They do not resolve by card order, grid position, array index, or old generated slugs. The same data is available as `juquilita_canonical_product_image_map.csv`.

Validate product images and write the final CSV report:

```bash
python3 scripts/validate_product_images.py
```

Validate storefront product prices against the original website menu:

```bash
python3 scripts/validate_prices.py
```

Report outputs:

```text
reports/product_image_validation_report.csv
reports/product_price_validation_report.csv
```

## v6 stabilization features

- Stripe Checkout Session adapter.
- Square hosted payment link adapter.
- Mock payment fallback for local development.
- Hosted payment links displayed to customers when deposit or full payment is required.
- Payment intent history, provider reference, provider response, status, and integration-event logging.
- Stripe webhook endpoint at `/api/webhooks/stripe`.
- SendGrid transactional email adapter.
- Twilio SMS adapter.
- Admin notification queue processor with dry-run and live-send modes.
- Secure password reset request and confirmation flow at `/reset.html`.
- Password reset tokens are stored as HMAC-SHA256 digests.
- Authenticator-app TOTP 2FA with recovery codes for staff/admin accounts.
- Optional global staff 2FA enforcement through the `admin_2fa_required` setting.
- Staff roles and permissions for owner, manager, cashier, baker, decorator, and wholesale manager.
- Admin route permission checks.
- Product photo upload plus photo shot-list tracking for true product photography.
- Supplier price quotes that can update ingredient unit cost after owner verification.
- Owner recipe verification records with yield, labor minutes, verifier, and notes.
- QA audit runs and checklist items for accessibility, mobile, security, and performance.
- Deep health endpoint at `/api/health/deep`.
- Admin-triggered SQLite backup with checksum.
- Command-line backup script at `scripts/backup_sqlite.py`.
- Simple monitor script at `scripts/monitor_check.py`.
- Static QA script at `scripts/qa_static_report.py`.
- Nginx, systemd, Certbot, and environment scaffolding under `deploy/`.

## Environment configuration

Copy `deploy/env.example` to `.env` or use your host's environment manager.

For production, set `JB_ENV=production`. Production mode fails fast unless HTTPS/public URL, secure cookies, `JB_SECRET_KEY`, `JB_TOKEN_PEPPER`, a non-mock payment provider, SendGrid, Twilio, and a real first owner account are configured. It also refuses to run a database that still contains the local demo accounts.

Stripe example:

```bash
JB_PUBLIC_BASE_URL=https://order.example.com
JB_PAYMENT_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_test_or_live_value
STRIPE_WEBHOOK_SECRET=whsec_test_or_live_value
```

Square example:

```bash
JB_PUBLIC_BASE_URL=https://order.example.com
JB_PAYMENT_PROVIDER=square
SQUARE_ACCESS_TOKEN=EAAA...
SQUARE_LOCATION_ID=LOCATION_ID
SQUARE_ENV=sandbox
SQUARE_WEBHOOK_SIGNATURE_KEY=replace-with-square-signature-key
SQUARE_WEBHOOK_NOTIFICATION_URL=https://order.example.com/api/webhooks/square
```

Email and SMS:

```bash
SENDGRID_API_KEY=SG...
SENDGRID_FROM_EMAIL=orders@example.com
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_PHONE=+14233079003
```

HTTPS production:

```bash
JB_SECURE_COOKIES=1
JB_ASSUME_HTTPS=1
```

## Admin workflow

1. Verify the product catalog and prices with the owner.
2. Upload true product photos.
3. Enter supplier price quotes from invoices or supplier sheets.
4. Verify recipes, yields, and labor minutes with the owner.
5. Configure SendGrid and Twilio.
6. Configure Stripe or Square in sandbox.
7. Set up staff accounts and 2FA.
8. Run backup and deep health checks.
9. Run accessibility, mobile, security, and performance QA.
10. Deploy behind HTTPS.
11. Pilot with staff, trusted customers, and premium buyers before public ordering.

## Documentation

```text
docs/V5_PRODUCTION_INTEGRATIONS.md
docs/V5_QA_SECURITY_BACKUP_PLAN.md
docs/PRODUCTION_CUTOVER.md
docs/RUNBOOK.md
```

## Remaining production work

The app now has integration paths and admin evidence tracking, but production still needs real vendor accounts, actual product photos, exact owner-approved costs and recipes, payment sandbox testing, webhook-signature verification, real device QA, accessibility remediation, off-server backup storage, live monitoring, staff onboarding, and demo credential removal.

## v6 added work

- Bakery-case browsing with visual shape filters.
- Seasonal capacity cards and pickup-window records.
- Product trust indicators for verification, photo readiness, and completeness.
- Checkout language and substitution preferences.
- Private receipt tokens instead of public short-code receipts.
- Quote request metadata for cake and seasonal review.
- Role-based production command center for cashier, baker, decorator, and wholesale manager.
- Manual refund records, tax export runs, and standing-order run generation.
- Documentation in `docs/V6_STABILIZATION_NOTES.md`.
