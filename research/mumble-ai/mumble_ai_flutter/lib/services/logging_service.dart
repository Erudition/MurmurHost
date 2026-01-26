import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

class LoggingService {
  static LoggingService? _instance;
  static LoggingService getInstance() {
    _instance ??= LoggingService._();
    return _instance!;
  }

  LoggingService._();

  final List<LogEntry> _logs = [];
  static const int maxLogs = 100; // Keep only last 100 logs
  static const String logsKey = 'app_logs';
  
  // Store ApiService reference for automatic log sending
  ApiService? _apiService;
  bool _isSendingLogs = false;

  // Log levels
  static const String levelDebug = 'DEBUG';
  static const String levelInfo = 'INFO';
  static const String levelWarning = 'WARNING';
  static const String levelError = 'ERROR';

  // Set ApiService reference for automatic log sending
  void setApiService(ApiService apiService) {
    _apiService = apiService;
  }

  void log(String level, String message, {String? screen, Map<String, dynamic>? data}) {
    final entry = LogEntry(
      timestamp: DateTime.now(),
      level: level,
      message: message,
      screen: screen,
      data: data,
    );

    _logs.add(entry);

    // Keep only the last maxLogs entries
    if (_logs.length > maxLogs) {
      _logs.removeAt(0);
    }

    // Print to console in debug mode
    if (kDebugMode) {
      print('[${entry.level}] ${entry.screen != null ? '[${entry.screen}] ' : ''}${entry.message}');
      if (entry.data != null) {
        print('Data: ${entry.data}');
      }
    }

    // Save to local storage
    _saveLogsToStorage();
    
    // Auto-send logs to server if we have enough logs (every 25 logs for comprehensive logging)
    if (_logs.length % 25 == 0) {
      _autoSendLogsToServer();
    }
  }

  void debug(String message, {String? screen, Map<String, dynamic>? data}) {
    log(levelDebug, message, screen: screen, data: data);
  }

  void info(String message, {String? screen, Map<String, dynamic>? data}) {
    log(levelInfo, message, screen: screen, data: data);
  }

  void warning(String message, {String? screen, Map<String, dynamic>? data}) {
    log(levelWarning, message, screen: screen, data: data);
  }

  void error(String message, {String? screen, Map<String, dynamic>? data}) {
    log(levelError, message, screen: screen, data: data);
    // Immediately send error logs to server
    _autoSendLogsToServer();
  }

  void logException(dynamic exception, StackTrace? stackTrace, {String? screen}) {
    error('Exception: ${exception.toString()}', 
          screen: screen, 
          data: {
            'exception': exception.toString(),
            'stackTrace': stackTrace?.toString(),
          });
    // Immediately send exception logs to server
    _autoSendLogsToServer();
  }

  List<LogEntry> getLogs() {
    return List.from(_logs);
  }

  List<LogEntry> getLogsByLevel(String level) {
    return _logs.where((log) => log.level == level).toList();
  }

  List<LogEntry> getLogsByScreen(String screen) {
    return _logs.where((log) => log.screen == screen).toList();
  }

  Future<void> _saveLogsToStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final logsJson = _logs.map((log) => log.toJson()).toList();
      await prefs.setString(logsKey, logsJson.toString());
    } catch (e) {
      if (kDebugMode) {
        print('Failed to save logs to storage: $e');
      }
    }
  }

  Future<void> loadLogsFromStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final logsString = prefs.getString(logsKey);
      if (logsString != null) {
        // Parse logs from storage (simplified - in real app you'd use proper JSON parsing)
        // For now, we'll just clear and start fresh
        _logs.clear();
      }
    } catch (e) {
      if (kDebugMode) {
        print('Failed to load logs from storage: $e');
      }
    }
  }

  Future<bool> sendLogsToServer(ApiService apiService) async {
    try {
      if (_logs.isEmpty) return true;

      final logsData = _logs.map((log) => log.toJson()).toList();
      
      final response = await apiService.post('/api/logs', data: {
        'logs': logsData,
        'device_info': {
          'platform': 'android',
          'timestamp': DateTime.now().toIso8601String(),
        }
      });

      if (response.statusCode == 200) {
        // Clear logs after successful send
        _logs.clear();
        await _saveLogsToStorage();
        return true;
      }
      return false;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to send logs to server: $e');
      }
      return false;
    }
  }

  void clearLogs() {
    _logs.clear();
    _saveLogsToStorage();
  }

  // Auto-send logs to server in background
  Future<void> _autoSendLogsToServer() async {
    // Prevent concurrent sends
    if (_isSendingLogs || _apiService == null || _logs.isEmpty) {
      return;
    }

    _isSendingLogs = true;
    
    try {
      final logsData = _logs.map((log) => log.toJson()).toList();
      
      final response = await _apiService!.post('/api/logs', data: {
        'logs': logsData,
        'device_info': {
          'platform': 'android',
          'timestamp': DateTime.now().toIso8601String(),
        }
      });

      if (response.statusCode == 200) {
        // Clear logs after successful send
        _logs.clear();
        await _saveLogsToStorage();
      }
    } catch (e) {
      // Silent fail for auto-send - don't want logging to break the app
      if (kDebugMode) {
        print('Auto-send logs failed: $e');
      }
    } finally {
      _isSendingLogs = false;
    }
  }

  // Log user actions
  void logUserAction(String action, {String? screen, Map<String, dynamic>? data}) {
    info('User Action: $action', screen: screen, data: data);
  }

  // Log navigation events
  void logNavigation(String from, String to, {Map<String, dynamic>? data}) {
    info('Navigation: $from -> $to', screen: from, data: data);
  }

  // Log API calls
  void logApiCall(String method, String endpoint, {dynamic requestData, dynamic responseData, int? statusCode}) {
    info('API Call: $method $endpoint', screen: 'ApiService', data: {
      'method': method,
      'endpoint': endpoint,
      'requestData': requestData,
      'responseData': responseData,
      'statusCode': statusCode,
    });
  }

  // Log screen lifecycle events
  void logScreenLifecycle(String screen, String event, {Map<String, dynamic>? data}) {
    info('Screen $event: $screen', screen: screen, data: data);
  }

  // Log performance metrics
  void logPerformance(String operation, Duration duration, {String? screen, Map<String, dynamic>? data}) {
    info('Performance: $operation took ${duration.inMilliseconds}ms', screen: screen, data: {
      'operation': operation,
      'duration_ms': duration.inMilliseconds,
      ...?data,
    });
  }
}

class LogEntry {
  final DateTime timestamp;
  final String level;
  final String message;
  final String? screen;
  final Map<String, dynamic>? data;

  LogEntry({
    required this.timestamp,
    required this.level,
    required this.message,
    this.screen,
    this.data,
  });

  Map<String, dynamic> toJson() {
    return {
      'timestamp': timestamp.toIso8601String(),
      'level': level,
      'message': message,
      'screen': screen,
      'data': data,
    };
  }

  factory LogEntry.fromJson(Map<String, dynamic> json) {
    return LogEntry(
      timestamp: DateTime.parse(json['timestamp']),
      level: json['level'],
      message: json['message'],
      screen: json['screen'],
      data: json['data'],
    );
  }

  @override
  String toString() {
    return '[${timestamp.toIso8601String()}] [$level] ${screen != null ? '[$screen] ' : ''}$message';
  }
}
