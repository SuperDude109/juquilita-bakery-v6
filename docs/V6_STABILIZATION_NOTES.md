# v6 stabilization notes

v6 focuses on making the bakery system easier to operate and safer to pilot. The work moves the storefront closer to a real Mexican bakery experience and adds controls for rush periods, seasonal preorders, wholesale runs, receipts, refunds, tax export records, and launch-mode discipline.

## Customer experience changes

- Bakery-case rail showing expected ready batches.
- Shop-by-shape filters for customers who recognize bread visually before they know the exact name.
- Product cards now show visual shape, verification state, and product completeness.
- Seasonal campaign capacity cards for Pan de Muerto and Rosca de Reyes.
- Checkout now records language and substitution preferences.
- Public receipt access now uses a long receipt token instead of a short order code.
- Order tracking still requires order code plus customer email.
- Quote requests capture complexity tier, servings, colors, pickup handling, reference-image URL, and inscription confirmation.

## Admin operations changes

- Production command center with role boards for cashier, baker, decorator, and wholesale manager.
- Production tasks are created automatically from orders and quote requests.
- Admins can move production tasks through todo, doing, blocked, done, or canceled.
- Product batch rows show bakery-case readiness planning.
- Seasonal campaign and pickup-window views help holiday capacity planning.
- Payment panel now includes manual refund records and tax export runs.
- Wholesale panel now generates standing-order runs for a chosen date range.
- Notification preferences and attempts are stored so failed or blocked messages can be audited.

## Launch posture

v6 keeps phase-one launch mode enabled by default. The recommended public pilot should still be limited to verified catalog items, guest pickup ordering, cake and seasonal quote requests, deposits, admin order queue, production tickets, receipts, and notifications.

## Still unfinished

Real owner verification, product photography, live provider account credentials, provider webhook testing, exact taxes, supplier invoices, real recipes, screen-reader QA, mobile device QA, HTTPS deployment, backups, monitoring, and removal of demo accounts remain required before public launch.
