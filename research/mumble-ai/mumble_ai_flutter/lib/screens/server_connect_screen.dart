import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/storage_service.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class ServerConnectScreen extends StatefulWidget {
  const ServerConnectScreen({Key? key}) : super(key: key);

  @override
  State<ServerConnectScreen> createState() => _ServerConnectScreenState();
}

class _ServerConnectScreenState extends State<ServerConnectScreen> {
  final _formKey = GlobalKey<FormState>();
  final _urlController = TextEditingController();
  bool _isLoading = false;
  bool _rememberServer = true;
  String? _errorMessage;
  String? _successMessage;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('ServerConnectScreen', 'initState');
    
    _loadSavedSettings();
  }

  Future<void> _loadSavedSettings() async {
    final storageService = Provider.of<StorageService>(context, listen: false);
    final savedUrl = await storageService.getServerUrl();
    final remember = await storageService.getRememberServer();
    
    if (savedUrl != null && remember) {
      _urlController.text = savedUrl;
    }
    
    setState(() {
      _rememberServer = remember;
    });
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  String? _validateUrl(String? value) {
    if (value == null || value.isEmpty) {
      return 'Please enter a server URL';
    }
    
    try {
      final uri = Uri.parse(value);
      if (!uri.hasScheme || (!uri.scheme.startsWith('http'))) {
        return 'Please enter a valid HTTP/HTTPS URL';
      }
      if (!uri.hasAuthority) {
        return 'Please enter a valid server address';
      }
    } catch (e) {
      return 'Please enter a valid URL';
    }
    
    return null;
  }

  Future<void> _testConnection() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _successMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final url = _urlController.text.trim();
      
      // Set the base URL temporarily for testing
      apiService.setBaseUrl(url);
      
      // Test connection
      final isConnected = await apiService.testConnection();
      
      if (isConnected) {
        setState(() {
          _successMessage = 'Connection successful!';
        });
      } else {
        setState(() {
          _errorMessage = 'Connection failed. Please check the server URL and ensure the server is running.';
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Connection error: ${e.toString()}';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _connect() async {
    if (!_formKey.currentState!.validate()) return;

    final loggingService = Provider.of<LoggingService>(context, listen: false);
    final startTime = DateTime.now();
    
    loggingService.logUserAction('Connect to Server', screen: 'ServerConnectScreen', data: {
      'url': _urlController.text.trim(),
      'rememberServer': _rememberServer,
    });

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _successMessage = null;
    });

    try {
      final storageService = Provider.of<StorageService>(context, listen: false);
      final apiService = Provider.of<ApiService>(context, listen: false);
      final url = _urlController.text.trim();
      
      // Test connection first
      apiService.setBaseUrl(url);
      final isConnected = await apiService.testConnection();
      
      if (!isConnected) {
        loggingService.warning('Connection test failed', screen: 'ServerConnectScreen', data: {
          'url': url,
        });
        
        setState(() {
          _errorMessage = 'Connection failed. Please check the server URL and ensure the server is running.';
        });
        return;
      }
      
      // Save settings if remember is enabled
      if (_rememberServer) {
        await storageService.setServerUrl(url);
        await storageService.setRememberServer(true);
      } else {
        await storageService.removeServerUrl();
        await storageService.setRememberServer(false);
      }
      
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Server Connection', duration, screen: 'ServerConnectScreen');
      loggingService.info('Successfully connected to server', screen: 'ServerConnectScreen', data: {
        'url': url,
        'rememberServer': _rememberServer,
      });
      
      // Navigate to user selection
      if (mounted) {
        loggingService.logNavigation('ServerConnectScreen', 'UserSelectionScreen');
        Navigator.pushReplacementNamed(context, '/user-selection');
      }
    } catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Server Connection (ERROR)', duration, screen: 'ServerConnectScreen');
      loggingService.logException(e, null, screen: 'ServerConnectScreen');
      
      setState(() {
        _errorMessage = 'Connection error: ${e.toString()}';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: AppTheme.primaryGradient,
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppTheme.spacingL),
              child: Card(
                elevation: AppTheme.elevationL,
                child: Padding(
                  padding: const EdgeInsets.all(AppTheme.spacingXL),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // App Icon and Title
                        const Icon(
                          Icons.mic,
                          size: 64,
                          color: AppTheme.primaryColor,
                        ),
                        const SizedBox(height: AppTheme.spacingM),
                        Text(
                          AppConstants.appName,
                          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            color: AppTheme.primaryColor,
                            fontWeight: FontWeight.bold,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: AppTheme.spacingS),
                        Text(
                          'Connect to your Mumble AI server',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: AppTheme.textSecondary,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: AppTheme.spacingXL),
                        
                        // Server URL Input
                        TextFormField(
                          controller: _urlController,
                          decoration: const InputDecoration(
                            labelText: 'Server URL',
                            hintText: 'http://192.168.1.100:5002',
                            prefixIcon: Icon(Icons.dns),
                          ),
                          keyboardType: TextInputType.url,
                          textInputAction: TextInputAction.done,
                          validator: _validateUrl,
                          onFieldSubmitted: (_) => _connect(),
                        ),
                        const SizedBox(height: AppTheme.spacingM),
                        
                        // Remember Server Checkbox
                        CheckboxListTile(
                          title: const Text('Remember server'),
                          subtitle: const Text('Save server URL for future use'),
                          value: _rememberServer,
                          onChanged: (value) {
                            setState(() {
                              _rememberServer = value ?? true;
                            });
                          },
                          contentPadding: EdgeInsets.zero,
                        ),
                        const SizedBox(height: AppTheme.spacingM),
                        
                        // Error Message
                        if (_errorMessage != null)
                          Container(
                            padding: const EdgeInsets.all(AppTheme.spacingM),
                            margin: const EdgeInsets.only(bottom: AppTheme.spacingM),
                            decoration: BoxDecoration(
                              color: AppTheme.errorColor.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(AppTheme.radiusM),
                              border: Border.all(color: AppTheme.errorColor.withOpacity(0.3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline, color: AppTheme.errorColor),
                                const SizedBox(width: AppTheme.spacingS),
                                Expanded(
                                  child: Text(
                                    _errorMessage!,
                                    style: const TextStyle(color: AppTheme.errorColor),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        
                        // Success Message
                        if (_successMessage != null)
                          Container(
                            padding: const EdgeInsets.all(AppTheme.spacingM),
                            margin: const EdgeInsets.only(bottom: AppTheme.spacingM),
                            decoration: BoxDecoration(
                              color: AppTheme.successColor.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(AppTheme.radiusM),
                              border: Border.all(color: AppTheme.successColor.withOpacity(0.3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.check_circle_outline, color: AppTheme.successColor),
                                const SizedBox(width: AppTheme.spacingS),
                                Expanded(
                                  child: Text(
                                    _successMessage!,
                                    style: const TextStyle(color: AppTheme.successColor),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        
                        // Buttons
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed: _isLoading ? null : _testConnection,
                                icon: _isLoading
                                    ? const SizedBox(
                                        width: 16,
                                        height: 16,
                                        child: CircularProgressIndicator(strokeWidth: 2),
                                      )
                                    : const Icon(Icons.wifi_find),
                                label: const Text('Test Connection'),
                              ),
                            ),
                            const SizedBox(width: AppTheme.spacingM),
                            Expanded(
                              child: ElevatedButton.icon(
                                onPressed: _isLoading ? null : _connect,
                                icon: _isLoading
                                    ? const SizedBox(
                                        width: 16,
                                        height: 16,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                        ),
                                      )
                                    : const Icon(Icons.login),
                                label: const Text('Connect'),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppTheme.spacingL),
                        
                        // Help Section
                        Container(
                          padding: const EdgeInsets.all(AppTheme.spacingM),
                          decoration: BoxDecoration(
                            color: AppTheme.backgroundColor,
                            borderRadius: BorderRadius.circular(AppTheme.radiusM),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Need help?',
                                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: AppTheme.spacingS),
                              const Text(
                                '• Make sure your Mumble AI server is running\n'
                                '• Check that the server URL is correct\n'
                                '• Ensure your device is on the same network\n'
                                '• Default port is usually 5002',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: AppTheme.textSecondary,
                                ),
                              ),
                              const SizedBox(height: AppTheme.spacingS),
                              TextButton.icon(
                                onPressed: () async {
                                  final url = _urlController.text.trim().isNotEmpty 
                                      ? _urlController.text.trim() 
                                      : 'http://localhost:5002';
                                  if (await canLaunchUrl(Uri.parse(url))) {
                                    await launchUrl(Uri.parse(url));
                                  }
                                },
                                icon: const Icon(Icons.open_in_browser, size: 16),
                                label: const Text('Open Web Panel'),
                                style: TextButton.styleFrom(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  minimumSize: Size.zero,
                                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
