# Local runbook

## Start fresh

```bash
python3 server.py --init-db
python3 server.py
```

## Verify

```bash
curl http://127.0.0.1:8000/api/health
python3 tests/smoke_test.py
```

## Admin workflows

1. Login at `/admin.html` with the admin demo account.
2. Review open orders.
3. Use Production to see upcoming units by product.
4. Use Products to change stock, price, lead time, or order mode.
5. Use Quotes to respond to custom cake or seasonal bread requests.
6. Use Wholesale to approve or decline premium customer applications.
7. Use Promotions to create temporary discounts with date and redemption limits.
8. Use Forecast to plan around events.
9. Use Partners to publish only businesses with consent.
10. Use Hours & settings before taking real orders.

## Production conversion checklist

- Replace local standard-library server with a production framework.
- Move secrets into environment variables.
- Use HTTPS and secure cookies.
- Add real payment/deposit provider.
- Add real email/SMS provider.
- Import POS and historical sales.
- Add backups and monitoring.
- Add owner-approved product photos.
- Add full accessibility testing.
- Add staff roles for cashier, baker, decorator, wholesale manager, and owner.
