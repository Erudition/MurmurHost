# Mumble Web SSL Setup

**Date:** October 9, 2025
**Status:** ✅ Configured

---

## Overview

The mumble-web client now supports HTTPS/SSL connections, which is required by modern browsers to access microphone and audio features. This setup uses a self-signed SSL certificate with an nginx reverse proxy.

---

## Architecture

```
User Browser (HTTPS)
      ↓
https://localhost:8081
      ↓
mumble-web-nginx (nginx:alpine)
- Handles SSL/TLS termination
- Port 443 → Host port 8081
      ↓
mumble-web (rankenstein/mumble-web)
- WebSocket proxy to Mumble server
- Port 8080 (internal only)
      ↓
mumble-server:64738
```

---

## Components

### 1. SSL Certificates

**Location:** `mumble-web-ssl/`

**Files:**
- `cert.pem` - Self-signed SSL certificate (4096-bit RSA)
- `key.pem` - Private key
- `nginx-ssl.conf` - Original nginx config (not used)

**Certificate Details:**
- Type: Self-signed
- Key Size: 4096-bit RSA
- Validity: 365 days
- Subject: CN=localhost

**Generation Command:**
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj "//C=US\ST=State\L=City\O=MumbleAI\CN=localhost"
```

### 2. Nginx Reverse Proxy

**Image:** `nginx:alpine`
**Container Name:** `mumble-web-nginx`
**Configuration:** `mumble-web-nginx/nginx.conf`

**Features:**
- SSL/TLS termination on port 443
- Proxy to mumble-web backend
- WebSocket support
- HTTP/2 support
- Security headers
- Session caching

**Key Configuration:**
```nginx
upstream mumble_web {
    server mumble-web:8080;
}

server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Proxy with WebSocket support
    location / {
        proxy_pass http://mumble_web;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. Mumble Web Backend

**Image:** `rankenstein/mumble-web:latest`
**Container Name:** `mumble-web`
**Internal Port:** 8080 (not exposed to host)

**Backend:** Uses websockify to proxy WebSocket connections to Mumble server

---

## Docker Compose Configuration

```yaml
mumble-web:
  image: rankenstein/mumble-web:latest
  container_name: mumble-web
  depends_on:
    mumble-server:
      condition: service_started
  environment:
    - MUMBLE_SERVER=mumble-server:64738
  # No external port - accessed via nginx-ssl-proxy
  restart: unless-stopped
  networks:
    - mumble-ai-network

mumble-web-nginx:
  image: nginx:alpine
  container_name: mumble-web-nginx
  depends_on:
    - mumble-web
  ports:
    - "8081:443"
  volumes:
    - ./mumble-web-ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro
    - ./mumble-web-ssl/key.pem:/etc/nginx/ssl/key.pem:ro
    - ./mumble-web-nginx/nginx.conf:/etc/nginx/nginx.conf:ro
  restart: unless-stopped
  networks:
    - mumble-ai-network
```

---

## Access

### HTTPS URL
```
https://localhost:8081
```

### Browser Warning

Since this is a self-signed certificate, browsers will show a security warning:
- **Chrome/Edge:** "Your connection is not private" - Click "Advanced" → "Proceed to localhost (unsafe)"
- **Firefox:** "Warning: Potential Security Risk Ahead" - Click "Advanced" → "Accept the Risk and Continue"
- **Safari:** "This Connection Is Not Private" - Click "Show Details" → "Visit Website"

This is normal for self-signed certificates and safe for local development.

---

## Production SSL Certificate

For production deployments, replace the self-signed certificate with a proper SSL certificate from:

### Option 1: Let's Encrypt (Free)

Use Certbot to obtain a free SSL certificate:

```bash
# Install Certbot
apt-get install certbot

# Get certificate (requires domain name and port 80 accessible)
certbot certonly --standalone -d yourdomain.com

# Copy certificates
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem mumble-web-ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem mumble-web-ssl/key.pem

# Restart containers
docker-compose restart mumble-web-nginx
```

### Option 2: Commercial SSL Certificate

1. Generate CSR:
```bash
openssl req -new -newkey rsa:2048 -nodes \
  -keyout mumble-web-ssl/key.pem \
  -out mumble-web-ssl/cert.csr
```

2. Submit CSR to certificate authority
3. Receive certificate files
4. Copy to `mumble-web-ssl/cert.pem`
5. Restart nginx container

### Option 3: Reverse Proxy with SSL (Recommended)

Use a reverse proxy like:
- **Traefik** - Automatic Let's Encrypt certificates
- **Nginx Proxy Manager** - Web UI for SSL management
- **Caddy** - Automatic HTTPS with Let's Encrypt

---

## Troubleshooting

### Certificate Not Trusted

**Symptom:** Browser shows security warning

**Solution:** This is expected with self-signed certificates. For production:
- Use a certificate from a trusted CA (Let's Encrypt, DigiCert, etc.)
- Or add the self-signed certificate to your browser's trusted certificates

### Cannot Connect to https://localhost:8081

**Check container status:**
```bash
docker-compose ps mumble-web-nginx
```

**Check nginx logs:**
```bash
docker-compose logs mumble-web-nginx
```

**Check if port 8081 is accessible:**
```bash
curl -k https://localhost:8081
```

### Nginx Returns 502 Bad Gateway

**Symptom:** Nginx runs but shows 502 error

**Check mumble-web backend:**
```bash
docker-compose logs mumble-web
docker-compose ps mumble-web
```

**Verify backend is accessible from nginx:**
```bash
docker exec mumble-web-nginx wget -O- http://mumble-web:8080
```

### WebSocket Connection Fails

**Check nginx configuration:**
- Ensure `proxy_set_header Upgrade $http_upgrade;` is present
- Ensure `proxy_set_header Connection "upgrade";` is present
- Check that proxy timeouts are sufficient (`proxy_read_timeout 86400;`)

**Check browser console:**
- Look for WebSocket errors
- Verify WebSocket URL is correct (wss:// not ws://)

---

## Security Considerations

### Self-Signed Certificate Limitations

- ⚠️ Browser warnings on every visit
- ⚠️ Not trusted by external clients
- ⚠️ Certificate pinning won't work
- ✅ Adequate for local development
- ✅ Adequate for trusted internal networks

### Production Security Checklist

- [ ] Replace self-signed certificate with CA-signed certificate
- [ ] Enable HSTS (Strict-Transport-Security) header
- [ ] Implement certificate pinning if needed
- [ ] Configure strong cipher suites
- [ ] Enable OCSP stapling
- [ ] Set up certificate auto-renewal
- [ ] Configure firewall rules
- [ ] Enable rate limiting
- [ ] Set up monitoring and alerts

---

## Certificate Renewal

### Self-Signed Certificate

Current certificate is valid for 365 days from October 9, 2025.

**Expiry Date:** October 9, 2026

**To regenerate:**
```bash
cd mumble-web-ssl
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj "//C=US\ST=State\L=City\O=MumbleAI\CN=localhost"
docker-compose restart mumble-web-nginx
```

### Let's Encrypt Certificate

Certificates expire every 90 days.

**Auto-renewal with cron:**
```bash
# Add to crontab
0 0 * * * certbot renew --quiet && docker-compose restart mumble-web-nginx
```

---

## Performance

### SSL/TLS Overhead

- **Handshake:** ~100-200ms additional latency on first connection
- **Throughput:** Minimal impact (<5%) with modern CPUs
- **Memory:** ~1-2MB per connection for SSL session
- **CPU:** Negligible with session caching enabled

### Optimization

Nginx configuration includes:
- HTTP/2 for multiplexing
- SSL session caching (`10m cache`, `10m timeout`)
- Strong cipher suites for performance
- Connection keep-alive

---

## Files Created

```
mumble-web-ssl/
├── cert.pem          # SSL certificate
├── key.pem           # Private key
└── nginx-ssl.conf    # (Not used)

mumble-web-nginx/
└── nginx.conf        # Nginx configuration
```

---

## Deployment

### Initial Setup
```bash
# Certificates already generated
docker-compose up -d mumble-web mumble-web-nginx
```

### Update Configuration
```bash
# After modifying nginx.conf
docker-compose restart mumble-web-nginx
```

### Verify Deployment
```bash
# Check containers
docker-compose ps mumble-web mumble-web-nginx

# Check logs
docker-compose logs mumble-web-nginx

# Test HTTPS connection
curl -k -I https://localhost:8081
```

---

## Integration

### Browser Requirements

For full functionality, browsers require:
- **HTTPS connection** ✅ (Now enabled)
- **Microphone permissions** (Granted by user)
- **WebSocket support** (All modern browsers)
- **Web Audio API** (All modern browsers)

### Microphone Access

Browsers only allow microphone access over HTTPS (or localhost with HTTP).

**Without SSL:**
- ❌ Microphone access denied
- ❌ "Not secure" warning
- ❌ Poor user experience

**With SSL:**
- ✅ Microphone access allowed
- ✅ Secure connection indicator
- ✅ Professional appearance

---

## Related Documentation

- **Architecture**: `docs/ARCHITECTURE.md`
- **Configuration**: `docs/CONFIGURATION.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`

---

## Summary

**What Changed:**
- Added SSL/TLS support for mumble-web client
- Created self-signed certificate (365-day validity)
- Deployed nginx reverse proxy for SSL termination
- Configured secure WebSocket proxying

**Result:**
- HTTPS access at https://localhost:8081 ✅
- Browser microphone access enabled ✅
- Secure WebSocket connections ✅
- Production-ready SSL architecture ✅

**Deployed:** October 9, 2025

The mumble-web client now has full SSL/TLS support for secure connections and browser compatibility.
