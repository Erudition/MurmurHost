# Landing Page Service

A comprehensive Node.js service that provides a beautiful landing page for the Mumble AI system with real-time service monitoring, APK downloads, and changelog display.

## Overview

The Landing Page Service serves as the main entry point for users to access the Mumble AI system. It provides:

- **Service Status Dashboard**: Real-time monitoring of all Mumble AI services
- **APK Downloads**: Download links for the Flutter Android app with QR codes
- **Changelog Display**: Automatic parsing and display of project changelogs
- **Quick Access Links**: Direct links to all web interfaces
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Dark Mode Support**: Toggle between light and dark themes

## Features

### Service Status Monitoring

- **Real-time Health Checks**: Monitors all 10 Mumble AI services
- **Response Time Tracking**: Displays service response times
- **Status Indicators**: Visual health status with color coding
- **Auto-refresh**: Updates every 30 seconds automatically
- **Error Handling**: Graceful handling of service failures

### APK Management

- **Automatic Discovery**: Scans for APK files in the build directory
- **File Information**: Displays file size, modification date, and metadata
- **QR Code Generation**: Generates QR codes for easy mobile downloads
- **Download Links**: Direct download URLs with proper MIME types
- **Mobile Optimization**: Responsive design for mobile devices

### Changelog System

- **Automatic Parsing**: Reads all `CHANGELOG_*.md` files from docs directory
- **Markdown Rendering**: Converts markdown to HTML with syntax highlighting
- **Date Sorting**: Displays changelogs sorted by date (newest first)
- **Component Categorization**: Groups changelogs by component name

### Quick Access

- **Web Control Panel**: Direct link to management interface
- **TTS Voice Generator**: Link to voice generation interface
- **Mumble Web Client**: Link to web-based Mumble client
- **GitHub Repository**: Link to source code repository

## Architecture

### Service Configuration

The service monitors the following Mumble AI components:

```javascript
const SERVICES = {
  'mumble-server': { 
    host: 'mumble-server', 
    port: 64738, 
    name: 'Mumble Server', 
    healthPath: '/',
    externalPort: 48000,
    checkMethod: 'tcp'
  },
  'faster-whisper': { 
    host: 'faster-whisper', 
    port: 5000, 
    name: 'Faster Whisper', 
    healthPath: '/health',
    externalPort: 5000
  },
  'piper-tts': { 
    host: 'piper-tts', 
    port: 5001, 
    name: 'Piper TTS', 
    healthPath: '/health',
    externalPort: 5001
  },
  'web-control-panel': { 
    host: 'web-control-panel', 
    port: 5002, 
    name: 'Web Control Panel', 
    healthPath: '/',
    externalPort: 5002
  },
  'tts-web-interface': { 
    host: 'tts-web-interface', 
    port: 5003, 
    name: 'TTS Voice Generator', 
    healthPath: '/health',
    externalPort: 5003
  },
  'silero-tts': { 
    host: 'silero-tts', 
    port: 5004, 
    name: 'Silero TTS', 
    healthPath: '/health',
    externalPort: 5004
  },
  'chatterbox-tts': { 
    host: 'chatterbox-tts', 
    port: 5005, 
    name: 'Chatterbox TTS', 
    healthPath: '/health',
    externalPort: 5005,
    allow503: true
  },
  'email-summary-service': { 
    host: 'email-summary-service', 
    port: 5006, 
    name: 'Email Summary Service', 
    healthPath: '/health',
    externalPort: 5006
  },
  'mumble-web': { 
    host: 'mumble-web-nginx', 
    port: 443, 
    name: 'Mumble Web', 
    healthPath: '/',
    externalPort: 8081,
    useHttps: true
  },
  'mumble-bot': { 
    host: 'mumble-bot', 
    port: 8080, 
    name: 'Mumble Bot', 
    healthPath: '/health',
    externalPort: 8082
  }
};
```

### Health Check Methods

The service supports multiple health check methods:

1. **HTTP Health Checks**: Standard HTTP GET requests to health endpoints
2. **TCP Connection Checks**: Direct TCP socket connections for services without HTTP endpoints
3. **HTTPS Support**: Handles self-signed certificates for HTTPS services
4. **503 Handling**: Special handling for services that return 503 when not fully ready

### Data Sources

- **APK Files**: Mounted from `./mumble_ai_flutter/build/app/outputs/flutter-apk/`
- **Changelog Files**: Mounted from `./docs/` directory
- **Service Status**: Real-time health checks via Docker network

## API Endpoints

### Service Status

**GET** `/api/status`

Returns real-time status of all Mumble AI services.

**Response:**
```json
{
  "timestamp": "2025-01-15T10:30:00.000Z",
  "services": [
    {
      "service": "mumble-server",
      "name": "Mumble Server",
      "port": 48000,
      "internalPort": 64738,
      "host": "mumble-server",
      "status": "healthy",
      "responseTime": "15ms",
      "details": { "message": "TCP connection successful" },
      "url": "mumble-server:64738",
      "method": "tcp"
    }
  ],
  "summary": {
    "total": 10,
    "healthy": 8,
    "running": 1,
    "unhealthy": 1
  }
}
```

### Changelog Data

**GET** `/api/changelog`

Returns parsed changelog data from all `CHANGELOG_*.md` files.

**Response:**
```json
[
  {
    "component": "Topic State And Search Improvements",
    "date": "January 15, 2025",
    "content": "<h1>Topic State & Search Improvements</h1>...",
    "filename": "CHANGELOG_TOPIC_STATE_AND_SEARCH_IMPROVEMENTS.md"
  }
]
```

### APK Files

**GET** `/api/apk`

Returns information about available APK files.

**Response:**
```json
[
  {
    "filename": "app-release.apk",
    "size": "25.4 MB",
    "sizeBytes": 26624000,
    "modified": "2025-01-15T09:15:00.000Z",
    "path": "/app/apk/app-release.apk"
  }
]
```

### Device IP

**GET** `/api/device-ip`

Returns the device IP address for download URLs.

**Response:**
```json
{
  "deviceIP": "192.168.1.100",
  "port": 5007,
  "downloadBaseUrl": "http://192.168.1.100:5007/download/apk/"
}
```

### QR Code Generation

**GET** `/api/qr/:filename`

Generates a QR code for APK download.

**Response:**
```json
{
  "filename": "app-release.apk",
  "downloadUrl": "http://192.168.1.100:5007/download/apk/app-release.apk",
  "qrCode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "deviceIP": "192.168.1.100"
}
```

### APK Download

**GET** `/download/apk/:filename`

Serves APK files for download.

**Response:** Binary APK file with appropriate headers.

### Health Check

**GET** `/health`

Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00.000Z",
  "uptime": 3600.5,
  "version": "1.0.0"
}
```

## Configuration

### Environment Variables

- `PORT`: Service port (default: 5007)
- `NODE_ENV`: Environment mode (development/production)
- `HOST_IP`: Host IP address for download URLs

### Docker Configuration

The service is configured in `docker-compose.yml`:

```yaml
landing-page:
  build:
    context: ./landing-page
    dockerfile: Dockerfile
  container_name: landing-page
  ports:
    - "5007:5007"
  environment:
    - NODE_ENV=production
    - PORT=5007
    - HOST_IP=${HOST_IP:-10.0.0.74}
  volumes:
    - ./mumble_ai_flutter/build/app/outputs/flutter-apk:/app/apk:ro
    - ./docs:/app/docs:ro
  restart: unless-stopped
  networks:
    - mumble-ai-network
  healthcheck:
    test: ["CMD", "node", "-e", "require('http').get('http://localhost:5007/health', (res) => { process.exit(res.statusCode === 200 ? 0 : 1) })"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 10s
```

## Dependencies

### Node.js Packages

- `express`: Web framework
- `axios`: HTTP client for health checks
- `qrcode`: QR code generation
- `fs-extra`: Enhanced file system operations
- `markdown-it`: Markdown parsing
- `cors`: Cross-origin resource sharing

### Package.json

```json
{
  "name": "mumble-ai-landing-page",
  "version": "1.0.0",
  "description": "Landing page service for Mumble AI system",
  "main": "app.js",
  "scripts": {
    "start": "node app.js",
    "dev": "nodemon app.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "axios": "^1.6.0",
    "qrcode": "^1.5.3",
    "fs-extra": "^11.1.1",
    "markdown-it": "^13.0.2",
    "cors": "^2.8.5"
  }
}
```

## Usage

### Accessing the Landing Page

1. **Start the service**: `docker-compose up -d landing-page`
2. **Open browser**: Navigate to `http://localhost:5007`
3. **View services**: Check real-time service status
4. **Download APK**: Use download links or QR codes for mobile app
5. **Read changelogs**: View recent project updates

### Service Monitoring

The landing page automatically:
- Checks service health every 30 seconds
- Updates status indicators in real-time
- Handles service failures gracefully
- Provides detailed error information

### Mobile App Distribution

1. **Build APK**: Build Flutter app to generate APK files
2. **Automatic Discovery**: Landing page finds APK files automatically
3. **QR Code Generation**: Generate QR codes for easy mobile downloads
4. **Direct Downloads**: Provide direct download links

## Troubleshooting

### Common Issues

#### Services Not Showing as Healthy

- Check Docker network connectivity
- Verify service health endpoints
- Check firewall settings
- Review service logs

#### APK Files Not Found

- Ensure Flutter app is built
- Check volume mount configuration
- Verify file permissions
- Check APK directory path

#### QR Codes Not Generating

- Verify QR code library installation
- Check network connectivity
- Ensure proper URL generation
- Review browser console for errors

#### Changelog Not Loading

- Check docs directory mount
- Verify changelog file format
- Ensure markdown parsing works
- Check file permissions

### Debug Information

Enable debug logging by setting environment variables:

```bash
DEBUG=landing-page:*
NODE_ENV=development
```

### Health Check Failures

If the service health check fails:

1. Check service logs: `docker-compose logs -f landing-page`
2. Verify port availability: `netstat -an | grep 5007`
3. Test health endpoint: `curl http://localhost:5007/health`
4. Check Docker container status: `docker-compose ps`

## Development

### Local Development

```bash
cd landing-page
npm install
npm run dev
```

### Building Docker Image

```bash
docker build -t mumble-ai-landing-page ./landing-page
```

### Testing

```bash
# Test health endpoint
curl http://localhost:5007/health

# Test service status
curl http://localhost:5007/api/status

# Test APK files
curl http://localhost:5007/api/apk

# Test changelog
curl http://localhost:5007/api/changelog
```

## Security Considerations

- **CORS Enabled**: Allows cross-origin requests
- **File Access**: Read-only access to APK and docs directories
- **Health Checks**: No sensitive information exposed
- **QR Codes**: Generate safe download URLs
- **Error Handling**: No sensitive data in error messages

## Performance

- **Caching**: Changelog and APK data cached in memory
- **Async Operations**: Non-blocking health checks
- **Efficient Parsing**: Fast markdown and QR code generation
- **Minimal Dependencies**: Lightweight service footprint

## Future Enhancements

- **Authentication**: Optional authentication for admin features
- **Analytics**: Usage statistics and monitoring
- **Customization**: Configurable themes and branding
- **Notifications**: Service status alerts
- **Backup**: APK file backup and versioning
