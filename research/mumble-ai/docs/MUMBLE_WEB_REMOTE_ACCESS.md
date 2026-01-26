# Mumble Web Remote Access Configuration

**Date:** October 9, 2025
**Status:** ✅ Fixed

---

## Issue

When accessing the mumble-web client remotely (e.g., `https://your-ip:8081`), the client was unable to connect to the Mumble server even though the SSL certificate was working correctly.

---

## Root Cause

The mumble-web client's default configuration hardcoded the connection port to `443` (standard HTTPS port). When accessing the web interface on a custom port like `8081`, the client still tried to connect back to port `443`, causing connection failures.

**Default Configuration:**
```javascript
'defaults': {
  'port': '443',  // ← Hardcoded to 443
  'address': window.location.hostname
}
```

**Problem Scenario:**
1. User accesses: `https://192.168.1.100:8081`
2. Web interface loads successfully
3. User clicks "Connect"
4. Client tries to connect to: `wss://192.168.1.100:443` ❌ (wrong port!)
5. Connection fails

---

## Solution

Created a `config.local.js` file that overrides the default port configuration to automatically use the current browser connection's port.

**Configuration Override:**
```javascript
// mumble-web-config/config.local.js
window.mumbleWebConfig = window.mumbleWebConfig || {};

Object.assign(window.mumbleWebConfig.defaults, {
  // Use window.location.port to get the current port
  'port': window.location.port || '443',
  'address': window.location.hostname
});
```

**How it Works:**
1. User accesses: `https://192.168.1.100:8081`
2. Web interface loads with `config.local.js`
3. JavaScript reads `window.location.port` → `"8081"`
4. User clicks "Connect"
5. Client connects to: `wss://192.168.1.100:8081` ✅ (correct!)
6. Connection succeeds

---

## Implementation

### 1. Configuration File

**Location:** `mumble-web-config/config.local.js`

**Content:**
```javascript
window.mumbleWebConfig = window.mumbleWebConfig || {};

Object.assign(window.mumbleWebConfig.defaults, {
  'port': window.location.port || '443',
  'address': window.location.hostname
});
```

### 2. Docker Compose Update

**Added volume mount to mumble-web container:**
```yaml
mumble-web:
  image: rankenstein/mumble-web:latest
  container_name: mumble-web
  volumes:
    - ./mumble-web-config/config.local.js:/home/node/dist/config.local.js:ro
  environment:
    - MUMBLE_SERVER=mumble-server:64738
  restart: unless-stopped
  networks:
    - mumble-ai-network
```

### 3. Deployment

```bash
# Restart container with new configuration
docker-compose stop mumble-web
docker-compose rm -f mumble-web
docker-compose up -d mumble-web
```

---

## Remote Access Instructions

### Access the Web Client

**From any device on your network:**

1. Get your server's IP address:
   ```bash
   # Windows
   ipconfig

   # Linux/Mac
   ip addr show
   ```

2. Open a browser and navigate to:
   ```
   https://YOUR_SERVER_IP:8081
   ```

   Examples:
   - `https://192.168.1.100:8081`
   - `https://10.0.0.74:8081`
   - `https://100.97.57.92:8081` (via Tailscale)

3. Accept the SSL certificate warning:
   - Click "Advanced" → "Proceed to YOUR_SERVER_IP (unsafe)"
   - This is normal for self-signed certificates

4. Grant microphone permissions when prompted

5. Enter your username

6. Click "Connect" - it will automatically connect to the correct port ✅

### Firewall Configuration

If accessing from another device, ensure port 8081 is open:

**Windows Firewall:**
```powershell
New-NetFirewallRule -DisplayName "Mumble Web HTTPS" -Direction Inbound -LocalPort 8081 -Protocol TCP -Action Allow
```

**Linux (ufw):**
```bash
sudo ufw allow 8081/tcp
```

**Linux (iptables):**
```bash
sudo iptables -A INPUT -p tcp --dport 8081 -j ACCEPT
```

---

## Testing

### Local Access
```
https://localhost:8081
```
- Should connect to: `wss://localhost:8081` ✅

### Remote Access (LAN)
```
https://192.168.1.100:8081
```
- Should connect to: `wss://192.168.1.100:8081` ✅

### Remote Access (VPN)
```
https://100.97.57.92:8081
```
- Should connect to: `wss://100.97.57.92:8081` ✅

### Verify Connection

**Check browser console (F12):**
- Look for WebSocket connection messages
- Should show: `WebSocket connection opened to wss://YOUR_IP:8081`

**Check server logs:**
```bash
docker-compose logs --tail=20 mumble-web
```

Expected output:
```
172.18.0.13: Plain non-SSL (ws://) WebSocket connection
connecting to: mumble-server:64738 (using SSL)
```

---

## Alternative: Fixed IP Configuration

If you want to hardcode a specific server address and port, edit `config.local.js`:

```javascript
window.mumbleWebConfig = window.mumbleWebConfig || {};

Object.assign(window.mumbleWebConfig.defaults, {
  'address': 'your-server.example.com',  // Fixed hostname/IP
  'port': '8081'                          // Fixed port
});
```

**Use Case:**
- Multiple reverse proxies
- Load balancers
- Custom domain with non-standard port

---

## Troubleshooting

### "Cannot connect to server"

**Check 1: Verify the web interface loads**
- Navigate to `https://your-ip:8081`
- If this fails, check nginx and SSL certificates

**Check 2: Check browser console (F12)**
- Look for WebSocket errors
- Verify connection URL is correct

**Check 3: Check server logs**
```bash
docker-compose logs mumble-web
docker-compose logs mumble-web-nginx
docker-compose logs mumble-server
```

**Check 4: Verify port is accessible**
```bash
# From client machine
telnet your-server-ip 8081

# Or use PowerShell
Test-NetConnection -ComputerName your-server-ip -Port 8081
```

### WebSocket connection fails

**Symptom:** Interface loads but can't connect

**Possible causes:**
1. Firewall blocking WebSocket upgrade
2. Reverse proxy not forwarding WebSocket headers
3. Port mismatch (config.local.js not loaded)

**Verify config.local.js is loaded:**
- Open browser console (F12)
- Type: `window.mumbleWebConfig.defaults`
- Check the `port` value - should match your access port

### SSL certificate issues

**Symptom:** "Your connection is not private"

**Solution:** This is expected with self-signed certificates
- Click "Advanced" → "Proceed"
- For production, use a proper SSL certificate

---

## Security Considerations

### Self-Signed Certificate

- ⚠️ Not trusted by browsers (requires manual acceptance)
- ⚠️ Vulnerable to MITM attacks on untrusted networks
- ✅ Adequate for home/internal networks
- ✅ Better than plain HTTP

### Production Recommendations

1. **Use a proper SSL certificate:**
   - Let's Encrypt (free)
   - Commercial certificate authority
   - Internal PKI/CA

2. **Configure firewall rules:**
   - Only allow trusted IP ranges
   - Use VPN for external access

3. **Enable authentication:**
   - Set Mumble server password
   - Use certificate-based auth

4. **Use reverse proxy:**
   - Nginx Proxy Manager
   - Traefik
   - Caddy

---

## Advanced Configuration

### Custom Server URL

You can configure mumble-web to connect to a different server:

**Edit `config.local.js`:**
```javascript
Object.assign(window.mumbleWebConfig.defaults, {
  'address': 'mumble.example.com',
  'port': '64738',  // Standard Mumble port
  'username': 'DefaultUser',
  'channelName': 'General'
});
```

### Hide Address/Port Fields

To lock the connection to a specific server:

```javascript
Object.assign(window.mumbleWebConfig.connectDialog, {
  'address': false,  // Hide address field
  'port': false,     // Hide port field
  'username': true,
  'password': true
});

Object.assign(window.mumbleWebConfig.defaults, {
  'address': 'your-server.com',
  'port': '48000',
  'joinDialog': true  // Show simple "Join Conference" button
});
```

### Matrix Widget Mode

For embedding in Matrix clients:

```javascript
Object.assign(window.mumbleWebConfig.defaults, {
  'matrix': true,
  'joinDialog': true
});
```

---

## Related Files

```
mumble-web-config/
└── config.local.js        # Configuration overrides

docker-compose.yml         # Volume mount configuration
```

---

## Related Documentation

- **SSL Setup**: `docs/MUMBLE_WEB_SSL_SETUP.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`

---

## Summary

**Issue:** Remote access to mumble-web failed due to hardcoded port 443

**Solution:** Created `config.local.js` to dynamically use current connection port

**Result:**
- Local access works: `https://localhost:8081` ✅
- Remote access works: `https://192.168.1.100:8081` ✅
- VPN access works: `https://100.97.57.92:8081` ✅
- Automatic port detection ✅
- No manual configuration needed ✅

**Deployed:** October 9, 2025

The mumble-web client now works correctly for both local and remote access with automatic port detection.
