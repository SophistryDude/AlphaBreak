# Nginx Config for SEO Routes

These routes power the programmatic ticker pages and competitive comparison
pages. Without these rewrites, `https://alphabreak.vip/stocks/AAPL` will 404
because nginx doesn't know to serve `index.html` for that path.

## Required nginx location blocks

Add these to the `server { ... }` block in `/etc/nginx/sites-available/frontend`
(or wherever the alphabreak.vip server block lives), **before** the default
`location /` block.

```nginx
# Programmatic ticker pages: /stocks/<TICKER>
# Served by the SPA — JS extracts the ticker from location.pathname, sets
# per-ticker meta tags, and deep-links into the Analyze tab.
location ~ ^/stocks/[A-Za-z0-9\-\.]+/?$ {
    try_files $uri /index.html;
    add_header Cache-Control "no-cache, must-revalidate" always;
}

# Competitive comparison pages: /compare/tradingview, /compare/seeking-alpha, /compare/bloomberg
location ~ ^/compare/(tradingview|seeking-alpha|bloomberg)/?$ {
    try_files $uri /index.html;
    add_header Cache-Control "no-cache, must-revalidate" always;
}

# Blog article deep links: /blog/<slug>
# Already used by blog-viewer.js — this just makes the URLs indexable.
location ~ ^/blog/[a-z0-9\-_]+/?$ {
    try_files $uri /blog-viewer.html;
}

# Expose sitemap.xml and robots.txt at the root
location = /sitemap.xml { root /home/ubuntu/AlphaBreak/frontend; }
location = /robots.txt  { root /home/ubuntu/AlphaBreak/frontend; }
```

## Apply the changes

```bash
# SSH to the box
ssh -i trading-db-key.pem ubuntu@alphabreak.vip

# Edit the nginx config
sudo nano /etc/nginx/sites-available/frontend

# Validate the config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

## Smoke tests after deploy

```bash
# Ticker pages
curl -I https://alphabreak.vip/stocks/AAPL   # expect 200
curl -I https://alphabreak.vip/stocks/NVDA   # expect 200
curl -I https://alphabreak.vip/stocks/FAKE   # expect 200 (client JS handles the 404 gracefully)

# Comparison pages
curl -I https://alphabreak.vip/compare/tradingview     # expect 200
curl -I https://alphabreak.vip/compare/seeking-alpha   # expect 200
curl -I https://alphabreak.vip/compare/bloomberg       # expect 200

# Static SEO files
curl https://alphabreak.vip/robots.txt    # expect Sitemap line
curl https://alphabreak.vip/sitemap.xml   # expect XML with ~50 URLs
```

## Submit to search engines after deploy

1. **Google Search Console** — Add the property for `alphabreak.vip`, verify via DNS TXT record or HTML file, then submit `https://alphabreak.vip/sitemap.xml`. Use "URL inspection" to request indexing for the top 5 ticker pages directly.

2. **Bing Webmaster Tools** — Same flow, submit the sitemap.

3. **Monitor indexing** — Within ~48 hours the ticker pages start showing up. Use `site:alphabreak.vip` in Google to confirm.

## Expanding the ticker list

`frontend/sitemap.xml` currently lists 20 ticker pages. Update that file (or
make it dynamically generated from a backend route) as the free tier grows.
Every additional ticker is one more indexable Google entry point for queries
like "AAPL stock analysis" or "NVDA trend break."
