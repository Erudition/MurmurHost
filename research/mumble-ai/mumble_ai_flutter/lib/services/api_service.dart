import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'logging_service.dart';
import '../utils/constants.dart';
import '../models/entity.dart';
import '../models/memory_status.dart';
import '../models/memory_stats.dart';
import '../models/consolidation_log.dart';

class ApiService {
  static ApiService? _instance;
  late Dio _dio;
  String? _baseUrl;

  ApiService._() {
    _dio = Dio();
    _dio.options.connectTimeout = 10000; // 10 seconds
    _dio.options.receiveTimeout = 10000; // 10 seconds
    _dio.options.sendTimeout = 10000; // 10 seconds
    
    // Add interceptors for logging in debug mode
    if (kDebugMode) {
      _dio.interceptors.add(LogInterceptor(
        requestBody: true,
        responseBody: true,
        error: true,
      ));
    }
    
    // Add response interceptor to transform host.docker.internal URLs
    // Temporarily disabled to debug API issues
    // _dio.interceptors.add(InterceptorsWrapper(
    //   onResponse: (response, handler) {
    //     try {
    //       // Transform any host.docker.internal URLs in the response
    //       response.data = _transformHostDockerInternal(response.data);
    //     } catch (e) {
    //       // If transformation fails, continue with original data
    //       if (kDebugMode) {
    //         print('Error in response interceptor: $e');
    //       }
    //     }
    //     handler.next(response);
    //   },
    // ));
  }

  static ApiService getInstance() {
    _instance ??= ApiService._();
    return _instance!;
  }

  void setBaseUrl(String url) {
    _baseUrl = url.endsWith('/') ? url.substring(0, url.length - 1) : url;
    _dio.options.baseUrl = _baseUrl!;
  }

  String? get baseUrl => _baseUrl;

  // Helper method to safely cast response data to Map<String, dynamic>
  Map<String, dynamic>? safeCastResponseData(dynamic data) {
    if (data == null) return null;
    if (data is Map<String, dynamic>) return data;
    if (data is Map) {
      final Map<String, dynamic> result = {};
      data.forEach((key, value) {
        result[key.toString()] = value;
      });
      return result;
    }
    return null;
  }

  // Helper method to safely cast list data
  List<dynamic>? safeCastListData(dynamic data) {
    if (data == null) return null;
    if (data is List<dynamic>) return data;
    if (data is List) {
      return List<dynamic>.from(data);
    }
    return null;
  }

  // Helper method to safely cast any response data
  dynamic safeCastAnyData(dynamic data) {
    if (data == null) return null;
    if (data is Map<String, dynamic>) return data;
    if (data is Map) {
      final Map<String, dynamic> result = {};
      data.forEach((key, value) {
        result[key.toString()] = safeCastAnyData(value);
      });
      return result;
    }
    if (data is List<dynamic>) return data;
    if (data is List) {
      return data.map((item) => safeCastAnyData(item)).toList();
    }
    
    // Don't log unexpected data types to avoid spam
    
    return data;
  }

  // Test connection to server
  Future<bool> testConnection() async {
    try {
      final response = await _dio.get('/api/stats');
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  // Generic GET request
  Future<Response> get(String path, {Map<String, dynamic>? queryParameters}) async {
    final loggingService = LoggingService.getInstance();
    final startTime = DateTime.now();
    
    try {
      loggingService.logApiCall('GET', path, requestData: queryParameters);
      final response = await _dio.get(path, queryParameters: queryParameters);
      
      // Log the actual response type and data for debugging
      loggingService.debug('Response data type: ${response.data.runtimeType}', screen: 'ApiService');
      final dataStr = response.data.toString();
      loggingService.debug('Response data: ${dataStr.substring(0, dataStr.length > 200 ? 200 : dataStr.length)}', screen: 'ApiService');
      
      final duration = DateTime.now().difference(startTime);
      loggingService.logApiCall('GET', path, 
          requestData: queryParameters, 
          responseData: response.data, 
          statusCode: response.statusCode);
      loggingService.logPerformance('GET $path', duration);
      
      // Return the response as-is, let each screen handle the data type
      return response;
    } on DioError catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('GET $path (ERROR)', duration);
      throw _handleError(e);
    } catch (e, stackTrace) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('GET $path (EXCEPTION)', duration);
      loggingService.logException(e, stackTrace, screen: 'ApiService');
      rethrow;
    }
  }

  // Generic POST request
  Future<Response> post(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    final loggingService = LoggingService.getInstance();
    final startTime = DateTime.now();
    
    try {
      loggingService.logApiCall('POST', path, requestData: data);
      final response = await _dio.post(path, data: data, queryParameters: queryParameters);
      
      final duration = DateTime.now().difference(startTime);
      loggingService.logApiCall('POST', path, 
          requestData: data, 
          responseData: response.data, 
          statusCode: response.statusCode);
      loggingService.logPerformance('POST $path', duration);
      
      return response;
    } on DioError catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('POST $path (ERROR)', duration);
      throw _handleError(e);
    }
  }

  // Special method for chat requests with extended timeout
  Future<Response> postChat(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    final loggingService = LoggingService.getInstance();
    final startTime = DateTime.now();
    
    try {
      loggingService.logApiCall('POST', path, requestData: data);
      
      // Create a temporary Dio instance with extended timeout for chat requests
      final chatDio = Dio();
      chatDio.options.baseUrl = _baseUrl ?? '';
      chatDio.options.connectTimeout = AppConstants.chatTimeout;
      chatDio.options.sendTimeout = AppConstants.chatTimeout;
      chatDio.options.receiveTimeout = AppConstants.chatTimeout;
      
      final response = await chatDio.post(path, data: data, queryParameters: queryParameters);
      
      final duration = DateTime.now().difference(startTime);
      loggingService.logApiCall('POST', path, 
          requestData: data, 
          responseData: response.data, 
          statusCode: response.statusCode);
      loggingService.logPerformance('POST $path', duration);
      
      return response;
    } on DioError catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('POST $path (ERROR)', duration);
      throw _handleError(e);
    }
  }

  // Generic PUT request
  Future<Response> put(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    try {
      return await _dio.put(path, data: data, queryParameters: queryParameters);
    } on DioError catch (e) {
      throw _handleError(e);
    }
  }

  // Generic DELETE request
  Future<Response> delete(String path, {Map<String, dynamic>? queryParameters}) async {
    try {
      return await _dio.delete(path, queryParameters: queryParameters);
    } on DioError catch (e) {
      throw _handleError(e);
    }
  }

  // Download file (for audio previews)
  Future<Response> download(String path, String savePath) async {
    try {
      return await _dio.download(path, savePath);
    } on DioError catch (e) {
      throw _handleError(e);
    }
  }

  // Handle Dio errors and convert to user-friendly messages
  Exception _handleError(DioError error) {
    final loggingService = LoggingService.getInstance();
    
    String userMessage;
    if (error.type == DioErrorType.connectTimeout ||
        error.type == DioErrorType.sendTimeout ||
        error.type == DioErrorType.receiveTimeout) {
      userMessage = 'Connection timeout. Please check your network connection.';
    } else if (error.type == DioErrorType.response) {
      final statusCode = error.response?.statusCode;
      
      // Try to parse new error format first
      final newFormatMessage = _parseNewErrorFormat(error.response?.data);
      if (newFormatMessage != null) {
        userMessage = newFormatMessage;
      } else {
        // Fallback to old format
        final message = error.response?.data?['error'] ?? 'Server error';
        userMessage = 'Server error ($statusCode): $message';
      }
    } else if (error.type == DioErrorType.cancel) {
      userMessage = 'Request was cancelled';
    } else if (error.type == DioErrorType.other) {
      if (error.message.contains('SocketException')) {
        userMessage = 'Unable to connect to server. Please check the server URL and your network connection.';
      } else {
        userMessage = 'Network error: ${error.message}';
      }
    } else {
      userMessage = 'An unexpected error occurred: ${error.message}';
    }
    
    // Enhanced error logging with more details
    loggingService.error('API Error: $userMessage', 
                        screen: 'ApiService',
                        data: {
                          'errorType': error.type.toString(),
                          'statusCode': error.response?.statusCode,
                          'requestPath': error.requestOptions.path,
                          'baseUrl': _baseUrl,
                          'requestMethod': error.requestOptions.method,
                          'requestData': error.requestOptions.data,
                          'responseData': error.response?.data,
                          'errorMessage': error.message,
                          'stackTrace': error.stackTrace?.toString(),
                        });
    
    return Exception(userMessage);
  }

  // Parse new error response format from /api/chat endpoint
  String? _parseNewErrorFormat(dynamic responseData) {
    if (responseData == null) return null;
    
    try {
      // Check if it's the new error format
      if (responseData is Map<String, dynamic>) {
        final success = responseData['success'];
        if (success == false && responseData.containsKey('error')) {
          final error = responseData['error'];
          if (error is Map<String, dynamic>) {
            final code = error['code'] ?? 'UNKNOWN_ERROR';
            final message = error['message'] ?? 'An error occurred';
            final details = error['details'];
            
            // Map error codes to user-friendly messages
            String userMessage = _mapErrorCodeToMessage(code, message);
            
            if (details != null && details.toString().isNotEmpty) {
              userMessage += '\n\nDetails: $details';
            }
            
            return userMessage;
          }
        }
      }
    } catch (e) {
      // If parsing fails, return null to use fallback
    }
    
    return null;
  }

  // Map error codes to user-friendly messages
  String _mapErrorCodeToMessage(String code, String message) {
    switch (code) {
      case 'MISSING_PARAMETER':
        return 'Missing required information. Please try again.';
      case 'INVALID_FORMAT':
        return 'Invalid data format. Please check your input.';
      case 'NOT_FOUND':
        return 'The requested information was not found.';
      case 'DATABASE_ERROR':
        return 'Database error. Please try again later.';
      case 'OLLAMA_ERROR':
        return 'AI service is currently unavailable. Please try again later.';
      case 'CONFIG_ERROR':
        return 'Server configuration error. Please contact support.';
      case 'CONTEXT_ERROR':
        return 'Failed to load your personal context. Please try again.';
      case 'INTERNAL_ERROR':
        return 'An internal server error occurred. Please try again later.';
      case 'HEALTH_CHECK_FAILED':
        return 'Server health check failed. Please try again later.';
      case 'TIMEOUT_ERROR':
        return 'Request timed out. The AI is taking longer than expected to respond. Please try again.';
      default:
        return message.isNotEmpty ? message : 'An unexpected error occurred.';
    }
  }

  // Helper method to recursively transform host.docker.internal URLs and fix data types
  dynamic _transformHostDockerInternal(dynamic data) {
    if (data == null) return data;
    
    // If no base URL is set, we can't transform, so return data as-is
    if (_baseUrl == null) return data;
    
    try {
      // Extract server IP from base URL (e.g., "192.168.1.100" from "http://192.168.1.100:5002")
      final serverUri = Uri.parse(_baseUrl!);
      final serverHost = serverUri.host;
      
      if (data is String) {
        // Only transform if the string contains host.docker.internal
        if (data.contains('host.docker.internal')) {
          return data.replaceAll('host.docker.internal', serverHost);
        }
        return data;
      } else if (data is Map) {
        // Convert Map<dynamic, dynamic> to Map<String, dynamic>
        final Map<String, dynamic> result = {};
        data.forEach((key, value) {
          final stringKey = key.toString();
          result[stringKey] = _transformHostDockerInternal(value);
        });
        return result;
      } else if (data is List) {
        return data.map((item) => _transformHostDockerInternal(item)).toList();
      }
    } catch (e) {
      // If there's any error parsing the URL, return data as-is
      if (kDebugMode) {
        print('Error transforming host.docker.internal URLs: $e');
      }
    }
    
    return data;
  }

  // Memory System API Methods

  /// Get memory system status
  Future<MemoryStatus> getMemoryStatus() async {
    try {
      final response = await get(AppConstants.memoryStatusEndpoint);
      return MemoryStatus.fromJson(response.data['data']);
    } catch (e) {
      rethrow;
    }
  }

  /// Get entities with optional filtering
  Future<Map<String, dynamic>> getEntities({
    int page = 1,
    int perPage = 20,
    String? userName,
    String? entityType,
    String? search,
  }) async {
    final queryParams = <String, dynamic>{
      'page': page,
      'per_page': perPage,
    };
    
    if (userName != null) queryParams['user_name'] = userName;
    if (entityType != null) queryParams['entity_type'] = entityType;
    if (search != null) queryParams['search'] = search;

    final response = await get(AppConstants.memoryEntitiesEndpoint, queryParameters: queryParams);
    return response.data;
  }

  /// Create a new entity
  Future<Entity> createEntity({
    required String entityText,
    required String entityType,
    required String userName,
    String? contextInfo,
    double confidence = 1.0,
  }) async {
    final data = {
      'entity_text': entityText,
      'entity_type': entityType,
      'user_name': userName,
      'context_info': contextInfo,
      'confidence': confidence,
    };

    final response = await post(AppConstants.memoryEntitiesEndpoint, data: data);
    return Entity.fromJson(response.data['data']);
  }

  /// Update an existing entity
  Future<Entity> updateEntity(int id, {
    String? entityText,
    String? contextInfo,
    double? confidence,
  }) async {
    final data = <String, dynamic>{};
    if (entityText != null) data['entity_text'] = entityText;
    if (contextInfo != null) data['context_info'] = contextInfo;
    if (confidence != null) data['confidence'] = confidence;

    final response = await put('${AppConstants.memoryEntitiesEndpoint}/$id', data: data);
    return Entity.fromJson(response.data['data']);
  }

  /// Delete an entity
  Future<void> deleteEntity(int id) async {
    await delete('${AppConstants.memoryEntitiesEndpoint}/$id');
  }

  /// Search memories using hybrid search
  Future<Map<String, dynamic>> searchMemories({
    required String query,
    int limit = 20,
    String? userName,
    String searchType = 'all',
  }) async {
    final queryParams = <String, dynamic>{
      'q': query,
      'limit': limit,
      'search_type': searchType,
    };
    
    if (userName != null) queryParams['user_name'] = userName;

    final response = await get(AppConstants.memorySearchEndpoint, queryParameters: queryParams);
    return response.data;
  }

  /// Get consolidation history and statistics
  Future<ConsolidationSummary> getConsolidationHistory() async {
    try {
      final response = await get(AppConstants.memoryConsolidationEndpoint);
      return ConsolidationSummary.fromJson(response.data['data']);
    } catch (e) {
      rethrow;
    }
  }

  /// Trigger manual consolidation for a user
  Future<Map<String, dynamic>> triggerConsolidation({
    required String userName,
    int cutoffDays = 7,
  }) async {
    final data = {
      'user_name': userName,
      'cutoff_days': cutoffDays,
    };

    final response = await post(AppConstants.memoryConsolidationRunEndpoint, data: data);
    return response.data;
  }

  /// Get memory context for a user
  Future<Map<String, dynamic>> getMemoryContext({
    required String userName,
    String? sessionId,
    bool includeEntities = true,
    bool includeConsolidated = true,
    int limit = 10,
  }) async {
    final queryParams = <String, dynamic>{
      'include_entities': includeEntities,
      'include_consolidated': includeConsolidated,
      'limit': limit,
    };
    
    if (sessionId != null) queryParams['session_id'] = sessionId;

    final response = await get('${AppConstants.memoryContextEndpoint}/$userName', queryParameters: queryParams);
    return response.data;
  }

  /// Get memory system statistics
  Future<MemoryStats> getMemoryStats() async {
    try {
      final response = await get(AppConstants.memoryStatsEndpoint);
      return MemoryStats.fromJson(response.data['data']);
    } catch (e) {
      rethrow;
    }
  }
}
