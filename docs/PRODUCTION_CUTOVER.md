# Production cutover checklist

## Runtime gate

Set `JB_ENV=production` before production initialization or runtime. In this mode the app refuses to start with demo credentials, mock payments, missing HTTPS settings, missing token pepper, placeholder secrets, or missing SendGrid/Twilio/payment credentials.

Generate independent random values for `JB_SECRET_KEY` and `JB_TOKEN_PEPPER`, then initialize the first production owner:

```bash
JB_ENV=production \
JB_PUBLIC_BASE_URL=https://order.example.com \
JB_SECURE_COOKIES=1 \
JB_ASSUME_HTTPS=1 \
JB_SECRET_KEY='replace-with-random-32-plus-chars' \
JB_TOKEN_PEPPER='replace-with-different-random-32-plus-chars' \
JB_PAYMENT_PROVIDER=stripe \
STRIPE_SECRET_KEY='sk_live_...' \
STRIPE_WEBHOOK_SECRET='whsec_...' \
SENDGRID_API_KEY='SG...' \
SENDGRID_FROM_EMAIL='orders@example.com' \
TWILIO_ACCOUNT_SID='AC...' \
TWILIO_AUTH_TOKEN='...' \
TWILIO_FROM_PHONE='+14233079003' \
JB_ADMIN_EMAIL='owner@example.com' \
JB_ADMIN_PASSWORD='strong-temporary-password' \
python3 server.py --init-db
```

Remove `JB_ADMIN_PASSWORD` from the runtime environment after initialization. The owner should sign in, change the password, and enable 2FA before public ordering.

1. Run owner catalog verification from the admin Verification tab.
2. Upload real photos for every featured product and every commonly ordered product.
3. Hide, retire, or mark quote-only any item the bakery cannot reliably fulfill online.
4. Configure actual sales tax after accountant review.
5. Replace all demo users and rotate the secret key.
6. Remove demo partner cards and publish only businesses with documented consent.
7. Configure Stripe or Square, then test deposits, full payments, refunds, and failed payments.
8. Configure email and SMS delivery.
9. Move from SQLite to PostgreSQL for production.
10. Add backups, monitoring, HTTPS, uptime alerts, and error logging.
11. Complete mobile QA and accessibility QA.
12. Pilot internally, then with trusted customers, then with premium shop buyers, then with limited public ordering.
