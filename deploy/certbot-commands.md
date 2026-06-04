# Certbot commands for Nginx

Replace `order.example.com` with the real ordering domain.

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/juquilita-bakery
sudo ln -s /etc/nginx/sites-available/juquilita-bakery /etc/nginx/sites-enabled/juquilita-bakery
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d order.example.com
sudo certbot renew --dry-run
```

After HTTPS is working, set:

```bash
JB_SECURE_COOKIES=1
JB_ASSUME_HTTPS=1
JB_PUBLIC_BASE_URL=https://order.example.com
```
