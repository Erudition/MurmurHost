# Landing Page Service & Flutter Android App

**Date**: January 15, 2025

## Overview

This update introduces two major new components to the Mumble AI system:

1. **Landing Page Service** - A comprehensive Node.js service providing a beautiful web interface for system access
2. **Flutter Android App** - A complete mobile application for managing the Mumble AI system remotely

## Landing Page Service (Port 5007)

### Features

#### Service Status Dashboard
- **Real-time Monitoring**: Monitors all 10 Mumble AI services with health checks
- **Response Time Tracking**: Displays service response times and status indicators
- **Auto-refresh**: Updates every 30 seconds automatically
- **Visual Status**: Color-coded health indicators (healthy/unhealthy/running)
- **Error Handling**: Graceful handling of service failures with detailed error information

#### APK Management System
- **Automatic Discovery**: Scans for APK files in the Flutter build directory
- **File Information**: Displays file size, modification date, and metadata
- **QR Code Generation**: Generates QR codes for easy mobile downloads
- **Download Links**: Direct download URLs with proper MIME types
- **Mobile Optimization**: Responsive design for mobile devices

#### Changelog Display
- **Automatic Parsing**: Reads all `CHANGELOG_*.md` files from docs directory
- **Markdown Rendering**: Converts markdown to HTML with syntax highlighting
- **Date Sorting**: Displays changelogs sorted by date (newest first)
- **Component Categorization**: Groups changelogs by component name

#### Quick Access Links
- **Web Control Panel**: Direct link to management interface (Port 5002)
- **TTS Voice Generator**: Link to voice generation interface (Port 5003)
- **Mumble Web Client**: Link to web-based Mumble client (Port 8081)
- **GitHub Repository**: Link to source code repository

### Technical Implementation

#### Service Architecture
- **Node.js/Express**: Lightweight web server with comprehensive API
- **Health Check Methods**: HTTP health checks, TCP connections, HTTPS support
- **Caching**: In-memory caching for changelog and APK data
- **Error Handling**: Comprehensive error handling and logging

#### API Endpoints
- `GET /api/status` - Service status monitoring
- `GET /api/changelog` - Changelog data
- `GET /api/apk` - APK file information
- `GET /api/qr/:filename` - QR code generation
- `GET /download/apk/:filename` - APK file downloads
- `GET /api/device-ip` - Device IP information
- `GET /health` - Service health check

#### Docker Integration
- **Container**: `landing-page` service in docker-compose.yml
- **Port**: 5007 (external), 5007 (internal)
- **Volumes**: APK files and docs directory mounted read-only
- **Health Check**: Built-in health check endpoint
- **Environment**: Configurable host IP for download URLs

## Flutter Android App

### Features

#### Complete Mobile Interface
- **Server Connection Management**: Save and manage Mumble AI server URL
- **AI Chat Interface**: Direct text chat with Ollama AI
- **Dashboard**: Statistics and upcoming events overview
- **Configuration Management**: All web panel features accessible via mobile

#### AI Configuration
- **Ollama Configuration**: Model and URL management for AI models
- **Vision Model Configuration**: Image analysis model settings
- **Memory Model Configuration**: Memory extraction model settings
- **Persona Management**: Edit and enhance bot persona with AI assistance

#### Communication Features
- **Email Settings**: Complete SMTP, IMAP, and auto-reply configuration
- **Email Logs**: View email history with filtering and retry functionality
- **Voice Configuration**: All TTS engines (Piper, Silero, Chatterbox) with audio preview
- **Audio Playback**: Preview voices before selection

#### Data Management
- **Conversation History**: View and manage conversation logs
- **Persistent Memories**: CRUD operations for AI memories
- **Schedule Manager**: Full calendar and event management
- **Advanced Settings**: Fine-tune AI behavior and memory limits

### Technical Implementation

#### Flutter Architecture
- **Framework**: Flutter 2.10.2 with Material Design
- **State Management**: Provider pattern
- **HTTP Client**: Dio for API communication
- **Local Storage**: SharedPreferences for settings
- **Audio Playback**: AudioPlayers for voice preview

#### Project Structure
```
lib/
├── main.dart                    # App entry point
├── models/                      # Data models
├── services/                    # API & business logic
├── screens/                     # UI screens
├── widgets/                     # Reusable widgets
└── utils/                       # Utilities
```

#### API Integration
- **Complete API Coverage**: All 50+ endpoints from web control panel
- **Error Handling**: Comprehensive error handling and user feedback
- **Loading States**: Loading indicators and skeleton screens
- **Form Validation**: Input validation and user guidance

#### Mobile Features
- **Navigation Drawer**: Complete menu system with all features
- **Responsive Design**: Works on all Android screen sizes
- **Dark Mode Support**: Consistent theming throughout
- **Offline Handling**: Graceful handling of network issues

## Integration & Deployment

### Docker Compose Updates
- **New Service**: Added `landing-page` service to docker-compose.yml
- **Volume Mounts**: APK files and docs directory mounted
- **Health Checks**: Built-in health monitoring
- **Network Integration**: Full integration with mumble-ai-network

### Documentation Updates
- **New Documentation**: Created `LANDING_PAGE_SERVICE.md` with comprehensive API documentation
- **Architecture Updates**: Updated `ARCHITECTURE.md` to include new services
- **API Documentation**: Updated `API.md` with landing page service endpoints
- **Service Count**: Updated from 13 to 14 primary services

### Git Configuration
- **Updated .gitignore**: Added Flutter-specific ignore patterns
- **Build Artifacts**: Proper handling of Flutter build outputs
- **Documentation**: Comprehensive README updates

## Usage Instructions

### Landing Page Access
1. **Start Services**: `docker-compose up -d`
2. **Access Landing Page**: Navigate to `http://localhost:5007`
3. **Monitor Services**: View real-time service status
4. **Download APK**: Use download links or QR codes for mobile app
5. **Read Changelogs**: View recent project updates

### Android App Installation
1. **Build APK**: Build Flutter app to generate APK files
2. **Download**: Use landing page download links or QR codes
3. **Install**: Enable "Install from unknown sources" and install APK
4. **Configure**: Enter Mumble AI server URL
5. **Start Using**: Access all features via mobile interface

## Benefits

### Landing Page Service
- **Centralized Access**: Single entry point for all system components
- **Service Monitoring**: Real-time visibility into system health
- **Mobile Distribution**: Easy APK distribution with QR codes
- **Documentation Access**: Centralized changelog and documentation
- **User Experience**: Beautiful, responsive interface

### Flutter Android App
- **Mobile Management**: Complete system management from mobile device
- **Remote Access**: Manage system from anywhere on the network
- **Native Experience**: Full-featured mobile app with native performance
- **Offline Capability**: Works with network connectivity issues
- **Consistent Interface**: Same features as web control panel

## Technical Specifications

### Landing Page Service
- **Port**: 5007
- **Technology**: Node.js, Express, Alpine.js, Tailwind CSS
- **Dependencies**: axios, qrcode, fs-extra, markdown-it, cors
- **Health Checks**: HTTP, TCP, HTTPS support
- **Caching**: In-memory for performance

### Flutter Android App
- **Target**: Android API level 21+ (Android 5.0+)
- **Framework**: Flutter 2.10.2
- **Dependencies**: Dio, SharedPreferences, AudioPlayers, Provider
- **Architecture**: MVVM with Provider state management
- **UI**: Material Design with custom theming

## Future Enhancements

### Landing Page Service
- **Authentication**: Optional authentication for admin features
- **Analytics**: Usage statistics and monitoring
- **Customization**: Configurable themes and branding
- **Notifications**: Service status alerts

### Flutter Android App
- **iOS Support**: Extend to iOS platform
- **Push Notifications**: Real-time system alerts
- **Offline Mode**: Enhanced offline functionality
- **Voice Commands**: Voice control integration

## Conclusion

The addition of the Landing Page Service and Flutter Android App significantly enhances the Mumble AI system's accessibility and usability. Users now have:

- **Centralized Access**: Beautiful landing page with service monitoring
- **Mobile Management**: Complete mobile app for remote system management
- **Easy Distribution**: QR code-based APK distribution
- **Comprehensive Documentation**: Integrated changelog and documentation access
- **Enhanced User Experience**: Modern, responsive interfaces

These additions make the Mumble AI system more accessible, user-friendly, and suitable for both technical and non-technical users.
