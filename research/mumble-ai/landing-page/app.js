const express = require('express');
const axios = require('axios');
const QRCode = require('qrcode');
const fs = require('fs-extra');
const path = require('path');
const MarkdownIt = require('markdown-it');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 5007;

// Enhanced logging middleware
app.use((req, res, next) => {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${req.method} ${req.url} - ${req.ip}`);
  next();
});

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Log startup information
console.log('='.repeat(60));
console.log('Mumble-AI Landing Page Service Starting...');
console.log(`Port: ${PORT}`);
console.log(`Node Version: ${process.version}`);
console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
console.log('='.repeat(60));

// Initialize markdown parser
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
});

// Service configuration - using container names for internal Docker network
const SERVICES = {
  'mumble-server': { 
    host: 'mumble-server', 
    port: 64738, 
    name: 'Mumble Server', 
    healthPath: '/',
    externalPort: 48000,
    checkMethod: 'tcp' // Mumble server doesn't have HTTP health endpoint
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
    allow503: true // This service returns 503 when not ready but is still running
  },
  'email-summary-service': {
    host: 'email-summary-service',
    port: 5006,
    name: 'Email Summary Service',
    healthPath: '/health',
    externalPort: 5006
  },
  'whisper-web-interface': {
    host: 'whisper-web-interface',
    port: 5008,
    name: 'Whisper Transcription',
    healthPath: '/health',
    externalPort: 5008
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

// Cache for changelog data
let changelogData = null;
let apkFiles = [];

// Initialize data on startup
async function initializeData() {
  console.log('Initializing landing page data...');
  try {
    console.log('Loading changelog data...');
    await loadChangelogData();
    console.log(`Loaded ${changelogData ? changelogData.length : 0} changelog entries`);
    
    console.log('Loading APK files...');
    await loadApkFiles();
    console.log(`Loaded ${apkFiles ? apkFiles.length : 0} APK files`);
    
    console.log('Landing page data initialized successfully');
  } catch (error) {
    console.error('Error initializing data:', error);
  }
}

// Load and parse changelog files
async function loadChangelogData() {
  try {
    const docsPath = path.join(__dirname, 'docs');
    console.log(`Reading docs directory: ${docsPath}`);
    
    const files = await fs.readdir(docsPath);
    console.log(`Found ${files.length} files in docs directory`);
    
    const changelogFiles = files.filter(file => file.startsWith('CHANGELOG_') && file.endsWith('.md'));
    console.log(`Found ${changelogFiles.length} changelog files:`, changelogFiles);
    
    const changelogs = [];
    
    for (const file of changelogFiles) {
      const filePath = path.join(docsPath, file);
      console.log(`Processing changelog file: ${file}`);
      
      const content = await fs.readFile(filePath, 'utf8');
      
      // Extract metadata from filename and content
      const component = file.replace('CHANGELOG_', '').replace('.md', '').replace(/_/g, ' ');
      const lines = content.split('\n');
      const title = lines.find(line => line.startsWith('**Date**:')) || 'Unknown Date';
      const date = title.replace('**Date**:', '').trim();
      
      changelogs.push({
        component,
        date,
        content: md.render(content),
        filename: file
      });
    }
    
    // Sort by date (newest first)
    changelogs.sort((a, b) => new Date(b.date) - new Date(a.date));
    changelogData = changelogs;
    
    console.log(`Successfully loaded ${changelogs.length} changelog entries`);
    
  } catch (error) {
    console.error('Error loading changelog data:', error);
    changelogData = [];
  }
}

// Load APK file information
async function loadApkFiles() {
  try {
    const apkPath = path.join(__dirname, 'apk');
    console.log(`Reading APK directory: ${apkPath}`);
    
    const files = await fs.readdir(apkPath);
    console.log(`Found ${files.length} files in APK directory:`, files);
    
    const apkFilesList = files.filter(file => file.endsWith('.apk'));
    console.log(`Found ${apkFilesList.length} APK files:`, apkFilesList);
    
    apkFiles = [];
    
    for (const file of apkFilesList) {
      const filePath = path.join(apkPath, file);
      console.log(`Processing APK file: ${file}`);
      
      const stats = await fs.stat(filePath);
      
      apkFiles.push({
        filename: file,
        size: formatFileSize(stats.size),
        sizeBytes: stats.size,
        modified: stats.mtime,
        path: filePath
      });
    }
    
    console.log(`Successfully loaded ${apkFiles.length} APK files`);
    
  } catch (error) {
    console.error('Error loading APK files:', error);
    apkFiles = [];
  }
}

// Helper function to format file size
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// TCP connection check function
async function checkTcpConnection(host, port, timeout = 5000) {
  return new Promise((resolve, reject) => {
    const net = require('net');
    const socket = new net.Socket();
    
    const timer = setTimeout(() => {
      socket.destroy();
      reject(new Error('Connection timeout'));
    }, timeout);
    
    socket.connect(port, host, () => {
      clearTimeout(timer);
      socket.destroy();
      resolve(true);
    });
    
    socket.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

// Check service health
async function checkServiceHealth(serviceName, config) {
  const startTime = Date.now();
  try {
    // Handle TCP-only services like mumble-server
    if (config.checkMethod === 'tcp') {
      console.log(`Checking TCP connection for ${serviceName} at ${config.host}:${config.port}`);
      await checkTcpConnection(config.host, config.port, 5000);
      const responseTime = Date.now() - startTime;
      console.log(`✓ ${serviceName} is healthy (${responseTime}ms) - TCP connection successful`);
      return {
        status: 'healthy',
        responseTime: `${responseTime}ms`,
        details: { message: 'TCP connection successful' },
        url: `${config.host}:${config.port}`,
        method: 'tcp'
      };
    }
    
    const protocol = config.useHttps ? 'https' : 'http';
    const url = `${protocol}://${config.host}:${config.port}${config.healthPath}`;
    console.log(`Checking health for ${serviceName} at ${url}`);
    
    const axiosConfig = { 
      timeout: 5000,
      headers: {
        'User-Agent': 'Mumble-AI-Landing-Page/1.0.0'
      }
    };
    
    // Handle HTTPS with self-signed certificates
    if (config.useHttps) {
      axiosConfig.httpsAgent = new (require('https').Agent)({
        rejectUnauthorized: false
      });
    }
    
    const response = await axios.get(url, axiosConfig);
    const responseTime = Date.now() - startTime;
    
    // Handle services that return 503 but are still considered healthy
    if (config.allow503 && response.status === 503) {
      console.log(`✓ ${serviceName} is running but not ready (${responseTime}ms) - 503 response`);
      return {
        status: 'running',
        responseTime: `${responseTime}ms`,
        details: response.data,
        url: url,
        note: 'Service running but not fully ready'
      };
    }
    
    // Handle 503 responses for chatterbox-tts specifically
    if (serviceName === 'chatterbox-tts' && response.status === 503) {
      console.log(`✓ ${serviceName} is running but not ready (${responseTime}ms) - 503 response`);
      return {
        status: 'running',
        responseTime: `${responseTime}ms`,
        details: response.data,
        url: url,
        note: 'Service running but not fully ready'
      };
    }
    
    console.log(`✓ ${serviceName} is healthy (${responseTime}ms)`);
    
    return {
      status: 'healthy',
      responseTime: `${responseTime}ms`,
      details: response.data,
      url: url
    };
  } catch (error) {
    const responseTime = Date.now() - startTime;
    
    // Handle 503 responses for chatterbox-tts specifically
    if (serviceName === 'chatterbox-tts' && error.response && error.response.status === 503) {
      console.log(`✓ ${serviceName} is running but not ready (${responseTime}ms) - 503 response`);
      return {
        status: 'running',
        responseTime: `${responseTime}ms`,
        details: error.response.data,
        url: `${config.useHttps ? 'https' : 'http'}://${config.host}:${config.port}${config.healthPath}`,
        note: 'Service running but not fully ready'
      };
    }
    
    // Handle specific error cases
    if (error.code === 'ECONNREFUSED') {
      console.log(`✗ ${serviceName} is not running (${responseTime}ms): Connection refused`);
      return {
        status: 'unhealthy',
        error: 'Service not running',
        responseTime: `${responseTime}ms`,
        details: null,
        url: `${config.useHttps ? 'https' : 'http'}://${config.host}:${config.port}${config.healthPath}`
      };
    }
    
    if (error.code === 'ENOTFOUND') {
      console.log(`✗ ${serviceName} host not found (${responseTime}ms): ${error.message}`);
      return {
        status: 'unhealthy',
        error: 'Host not found',
        responseTime: `${responseTime}ms`,
        details: null,
        url: `${config.useHttps ? 'https' : 'http'}://${config.host}:${config.port}${config.healthPath}`
      };
    }
    
    console.log(`✗ ${serviceName} is unhealthy (${responseTime}ms): ${error.message}`);
    
    return {
      status: 'unhealthy',
      error: error.message,
      responseTime: `${responseTime}ms`,
      details: null,
      url: `${config.useHttps ? 'https' : 'http'}://${config.host}:${config.port}${config.healthPath}`
    };
  }
}

// Routes

// Main landing page
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'index.html'));
});

// API: Service status
app.get('/api/status', async (req, res) => {
  console.log('API: Service status requested');
  try {
    const statusPromises = Object.entries(SERVICES).map(async ([serviceName, config]) => {
      const health = await checkServiceHealth(serviceName, config);
      return {
        service: serviceName,
        name: config.name,
        port: config.externalPort,
        internalPort: config.port,
        host: config.host,
        ...health
      };
    });
    
    const statuses = await Promise.all(statusPromises);
    const healthyCount = statuses.filter(s => s.status === 'healthy').length;
    const runningCount = statuses.filter(s => s.status === 'running').length;
    const unhealthyCount = statuses.filter(s => s.status === 'unhealthy').length;
    
    console.log(`Service status check complete: ${healthyCount} healthy, ${runningCount} running, ${unhealthyCount} unhealthy`);
    
    res.json({
      timestamp: new Date().toISOString(),
      services: statuses,
      summary: {
        total: statuses.length,
        healthy: healthyCount,
        running: runningCount,
        unhealthy: unhealthyCount
      }
    });
  } catch (error) {
    console.error('Error in service status API:', error);
    res.status(500).json({ error: error.message });
  }
});

// API: Changelog data
app.get('/api/changelog', (req, res) => {
  console.log('API: Changelog data requested');
  res.json(changelogData || []);
});

// API: APK files
app.get('/api/apk', (req, res) => {
  console.log('API: APK files requested');
  res.json(apkFiles);
});

// API: Get device IP
app.get('/api/device-ip', (req, res) => {
  const deviceIP = getDeviceIP(req);
  console.log(`Device IP requested: ${deviceIP}`);
  res.json({
    deviceIP: deviceIP,
    port: PORT,
    downloadBaseUrl: `${req.protocol}://${deviceIP}:${PORT}/download/apk/`
  });
});

// Get device IP address
function getDeviceIP(req) {
  console.log('Getting device IP from request headers:', {
    'x-forwarded-for': req.headers['x-forwarded-for'],
    'x-real-ip': req.headers['x-real-ip'],
    'x-client-ip': req.headers['x-client-ip'],
    'remote-address': req.connection.remoteAddress || req.socket.remoteAddress,
    'host': req.headers.host
  });
  
  // Try to get the real IP from various headers
  const forwarded = req.headers['x-forwarded-for'];
  const realIP = req.headers['x-real-ip'];
  const clientIP = req.headers['x-client-ip'];
  const remoteAddress = req.connection.remoteAddress || req.socket.remoteAddress;
  
  // Check forwarded header first
  if (forwarded) {
    const ip = forwarded.split(',')[0].trim();
    console.log(`Using forwarded IP: ${ip}`);
    return ip;
  }
  
  // Check real IP header
  if (realIP) {
    console.log(`Using real IP: ${realIP}`);
    return realIP;
  }
  
  // Check client IP header
  if (clientIP) {
    console.log(`Using client IP: ${clientIP}`);
    return clientIP;
  }
  
  // Check remote address
  if (remoteAddress) {
    // Remove IPv6 prefix if present
    const ip = remoteAddress.replace(/^::ffff:/, '');
    console.log(`Remote address: ${ip}`);
    
    // If it's a Docker internal IP or localhost, try to get the host IP from environment
    if (ip.startsWith('172.') || ip.startsWith('192.168.') || ip === '127.0.0.1' || ip === '::1') {
      const hostIP = process.env.HOST_IP;
      if (hostIP && hostIP !== 'localhost') {
        console.log(`Using HOST_IP environment variable: ${hostIP}`);
        return hostIP;
      }
      console.log(`Docker internal IP detected, using localhost fallback`);
      return 'localhost';
    }
    console.log(`Using remote address: ${ip}`);
    return ip;
  }
  
  // Final fallback
  console.log('No IP detected, using localhost fallback');
  return 'localhost';
}

// API: Generate QR code for APK
app.get('/api/qr/:filename', async (req, res) => {
  try {
    const filename = req.params.filename;
    console.log(`API: QR code requested for ${filename}`);
    
    const apkFile = apkFiles.find(file => file.filename === filename);
    
    if (!apkFile) {
      console.log(`APK file not found: ${filename}`);
      return res.status(404).json({ error: 'APK file not found' });
    }
    
    // Get device IP address instead of hostname
    const deviceIP = getDeviceIP(req);
    const downloadUrl = `${req.protocol}://${deviceIP}:${PORT}/download/apk/${filename}`;
    console.log(`Generating QR code for download URL: ${downloadUrl}`);
    
    // Generate QR code as PNG
    const qrCodeDataURL = await QRCode.toDataURL(downloadUrl, {
      width: 300,
      margin: 2,
      color: {
        dark: '#000000',
        light: '#FFFFFF'
      }
    });
    
    console.log(`QR code generated successfully for ${filename}`);
    res.json({
      filename,
      downloadUrl,
      qrCode: qrCodeDataURL,
      deviceIP: deviceIP
    });
  } catch (error) {
    console.error(`Error generating QR code for ${req.params.filename}:`, error);
    res.status(500).json({ error: error.message });
  }
});

// Serve APK files
app.get('/download/apk/:filename', (req, res) => {
  const filename = req.params.filename;
  console.log(`APK download requested: ${filename}`);
  
  const apkFile = apkFiles.find(file => file.filename === filename);
  
  if (!apkFile) {
    console.log(`APK file not found for download: ${filename}`);
    return res.status(404).send('APK file not found');
  }
  
  console.log(`Serving APK file: ${filename} (${apkFile.size})`);
  res.download(apkFile.path, filename, (err) => {
    if (err) {
      console.error('Error downloading APK:', err);
      res.status(500).send('Error downloading file');
    } else {
      console.log(`APK download completed: ${filename}`);
    }
  });
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    version: '1.0.0'
  });
});

// Start server
const server = app.listen(PORT, '0.0.0.0', () => {
  console.log('='.repeat(60));
  console.log('🚀 Mumble-AI Landing Page Service Started Successfully!');
  console.log(`📡 Server listening on 0.0.0.0:${PORT}`);
  console.log(`🌐 Accessible from: http://localhost:${PORT}`);
  console.log(`🔗 Health check: http://localhost:${PORT}/health`);
  console.log(`📊 Service status: http://localhost:${PORT}/api/status`);
  console.log('='.repeat(60));
  
  // Initialize data after server starts
  initializeData();
});

// Enhanced error handling
server.on('error', (error) => {
  console.error('❌ Server error:', error);
  if (error.code === 'EADDRINUSE') {
    console.error(`Port ${PORT} is already in use. Please choose a different port.`);
  }
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('🛑 SIGTERM received, shutting down gracefully...');
  server.close(() => {
    console.log('✅ Server closed successfully');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('🛑 SIGINT received, shutting down gracefully...');
  server.close(() => {
    console.log('✅ Server closed successfully');
    process.exit(0);
  });
});

module.exports = app;
