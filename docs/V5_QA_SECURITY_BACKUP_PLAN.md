# v5 QA, security, backup, and deployment plan

## Accessibility QA

Implemented:

- Static QA run records for accessibility, mobile, security, and performance.
- QA checklist items with pass, fail, manual, and not applicable statuses.
- Admin panel to run and update QA evidence.
- Target setting seeded as WCAG 2.2 AA.

Manual QA that still has to happen:

- Keyboard navigation through storefront, cart, checkout, auth dialogs, quote form, and admin console.
- Screen reader testing on key flows.
- Focus visibility review.
- Form label review.
- Color contrast review.
- Error-message clarity review.
- Spanish and English language review.

## Mobile QA

Implemented:

- Mobile breakpoint setting: 360, 390, 430, 768, and 1024 pixels.
- Static mobile checklist items.
- Admin QA evidence table.

Manual QA that still has to happen:

- iPhone Safari checkout.
- Android Chrome checkout.
- Cart drawer usability.
- Product filtering and photo browsing.
- Admin order queue on tablet.
- Kitchen ticket and label print tests.

## HTTPS deployment

Included deployment scaffolding:

- `deploy/nginx.conf`
- `deploy/juquilita-bakery.service`
- `deploy/env.example`
- `deploy/certbot-commands.md`

Production target:

- Nginx handles TLS and reverse proxy.
- App runs behind localhost only.
- `JB_SECURE_COOKIES=1` after HTTPS is active.
- `JB_PUBLIC_BASE_URL` must match the public HTTPS URL.

## Backups

Implemented:

- Admin-triggered SQLite hot backup using Python's SQLite backup support.
- Backup metadata table with status, size, checksum, notes, start time, finish time, and reason.
- `scripts/backup_sqlite.py` for command-line backup automation.

Production target:

- Run backups on a schedule.
- Copy backups off-server.
- Test restore monthly.
- Move to PostgreSQL when order volume or staff workflow requires it.

## Monitoring

Implemented:

- `/api/health` lightweight health endpoint.
- `/api/health/deep` database, provider, email, and SMS readiness endpoint.
- Monitoring events table.
- File logging under `logs/`.
- `scripts/monitor_check.py` for simple uptime checks.

Production target:

- Add Sentry DSN or another error tracker.
- Add uptime monitoring from outside the server.
- Alert the owner or developer on payment, SMS, email, and backup failures.

## Cutover order

1. Verify owner catalog and prices.
2. Upload real product photos.
3. Configure email and SMS sandbox tests.
4. Configure payment sandbox tests.
5. Enable staff accounts and 2FA.
6. Run accessibility and mobile QA.
7. Deploy behind HTTPS.
8. Enable backups and monitoring.
9. Pilot with staff only.
10. Pilot with five trusted customers.
11. Pilot with two wholesale customers.
12. Open one product category publicly.
