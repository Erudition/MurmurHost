import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'logging_service.dart';
import '../utils/constants.dart';
import '../models/transcription.dart';
import '../models/ai_content.dart';
import '../models/transcription_segment.dart';

class WhisperService {
  static WhisperService? _instance;
  late Dio _dio;
  String? _baseUrl;
  final LoggingService _loggingService = LoggingService.getInstance();

  WhisperService._() {
    _dio = Dio();
    _dio.options.connectTimeout = 30000; // 30 seconds
    _dio.options.receiveTimeout = 300000; // 5 minutes for transcription
    _dio.options.sendTimeout = 300000; // 5 minutes for uploads

    // Add interceptors for logging in debug mode
    if (kDebugMode) {
      _dio.interceptors.add(LogInterceptor(
        requestBody: true,
        responseBody: true,
        error: true,
      ));
    }
  }

  static WhisperService getInstance() {
    _instance ??= WhisperService._();
    return _instance!;
  }

  /// Set base URL using server IP from ApiService
  /// Constructs: http://SERVER_IP:5008
  void setBaseUrl(String serverIp) {
    // Extract IP from URL if full URL is provided
    try {
      final uri = Uri.parse(serverIp);
      final ip = uri.host;
      _baseUrl = 'http://$ip:${AppConstants.whisperPort}';
    } catch (e) {
      // If parsing fails, assume it's just an IP address
      _baseUrl = 'http://$serverIp:${AppConstants.whisperPort}';
    }
    _dio.options.baseUrl = _baseUrl!;
    _loggingService.info('Whisper service base URL set to: $_baseUrl', screen: 'WhisperService');
  }

  String? get baseUrl => _baseUrl;

  // Generic GET request
  Future<Response> _get(String path, {Map<String, dynamic>? queryParameters}) async {
    try {
      _loggingService.logApiCall('GET', path, requestData: queryParameters);
      final response = await _dio.get(path, queryParameters: queryParameters);
      _loggingService.logApiCall('GET', path,
          requestData: queryParameters,
          responseData: response.data,
          statusCode: response.statusCode);
      return response;
    } on DioError catch (e) {
      throw _handleError(e);
    }
  }

  // Generic POST request
  Future<Response> _post(String path, {dynamic data}) async {
    try {
      _loggingService.logApiCall('POST', path, requestData: data);
      final response = await _dio.post(path, data: data);
      _loggingService.logApiCall('POST', path,
          requestData: data,
          responseData: response.data,
          statusCode: response.statusCode);
      return response;
    } on DioError catch (e) {
      throw _handleError(e);
    }
  }

  // Generic DELETE request
  Future<Response> _delete(String path) async {
    try {
      _loggingService.logApiCall('DELETE', path);
      final response = await _dio.delete(path);
      _loggingService.logApiCall('DELETE', path,
          responseData: response.data,
          statusCode: response.statusCode);
      return response;
    } on DioError catch (e) {
      throw _handleError(e);
    }
  }

  /// Get list of transcriptions with pagination and search
  Future<Map<String, dynamic>> getTranscriptions({
    int page = 1,
    int perPage = 10,
    String? search,
  }) async {
    final queryParams = <String, dynamic>{
      'page': page,
      'per_page': perPage,
    };
    if (search != null && search.isNotEmpty) {
      queryParams['search'] = search;
    }

    final response = await _get(AppConstants.whisperTranscriptionsEndpoint, queryParameters: queryParams);

    final transcriptions = (response.data['transcriptions'] as List<dynamic>)
        .map((t) => Transcription.fromJson(t))
        .toList();

    return {
      'transcriptions': transcriptions,
      'total': response.data['total'] ?? 0,
      'page': response.data['page'] ?? 1,
      'per_page': response.data['per_page'] ?? perPage,
    };
  }

  /// Get detailed transcription with segments
  Future<DetailedTranscription> getTranscription(int id) async {
    final response = await _get('${AppConstants.whisperTranscriptionsEndpoint}/$id');
    return DetailedTranscription.fromJson(response.data['transcription']);
  }

  /// Delete a transcription
  Future<void> deleteTranscription(int id) async {
    await _delete('${AppConstants.whisperTranscriptionsEndpoint}/$id');
  }

  /// Upload audio/video file for transcription
  Future<Map<String, dynamic>> uploadFile(String filePath) async {
    try {
      final fileName = filePath.split('/').last;
      final formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(filePath, filename: fileName),
      });

      _loggingService.info('Uploading file: $fileName', screen: 'WhisperService');
      final response = await _dio.post(
        AppConstants.whisperUploadEndpoint,
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
        ),
      );
      _loggingService.info('File uploaded successfully', screen: 'WhisperService');
      return response.data;
    } on DioError catch (e) {
      throw _handleError(e);
    }
  }

  /// Transcribe uploaded file
  Future<Map<String, dynamic>> transcribeFile(Map<String, dynamic> fileData) async {
    final response = await _post(AppConstants.whisperTranscribeEndpoint, data: fileData);
    return response.data;
  }

  /// Generate AI content for a transcription
  Future<AIContent> generateAIContent({
    required int transcriptionId,
    required String transcriptionText,
    required String generationType,
  }) async {
    final response = await _post(
      AppConstants.whisperGenerateAIContentEndpoint,
      data: {
        'transcription_id': transcriptionId,
        'transcription_text': transcriptionText,
        'generation_type': generationType,
      },
    );

    if (response.data['success'] == true) {
      return AIContent.fromJson(response.data['ai_content']);
    } else {
      throw Exception(response.data['error'] ?? 'Failed to generate AI content');
    }
  }

  /// Get AI content for a transcription
  Future<Map<String, List<AIContent>>> getAIContent(int transcriptionId) async {
    final response = await _get('${AppConstants.whisperGetAIContentEndpoint}/$transcriptionId');

    final Map<String, List<AIContent>> aiContent = {};
    if (response.data['ai_content'] != null) {
      final contentMap = response.data['ai_content'] as Map<String, dynamic>;
      contentMap.forEach((type, contentList) {
        if (contentList is List) {
          aiContent[type] = contentList.map((c) => AIContent.fromJson(c)).toList();
        }
      });
    }

    return aiContent;
  }

  /// Regenerate title for a transcription
  Future<String> regenerateTitle(int transcriptionId, String transcriptionText) async {
    final response = await _post(
      AppConstants.whisperRegenerateTitleEndpoint,
      data: {
        'transcription_id': transcriptionId,
        'transcription_text': transcriptionText,
      },
    );

    if (response.data['success'] == true) {
      return response.data['title'] ?? '';
    } else {
      throw Exception(response.data['error'] ?? 'Failed to regenerate title');
    }
  }

  /// Get Whisper settings (Ollama configuration)
  Future<Map<String, dynamic>> getSettings() async {
    final response = await _get(AppConstants.whisperSettingsEndpoint);
    return response.data['settings'] ?? {};
  }

  /// Update Whisper settings
  Future<bool> updateSettings(Map<String, dynamic> settings) async {
    final response = await _post(AppConstants.whisperSettingsEndpoint, data: settings);
    return response.data['success'] == true;
  }

  /// Get available Ollama models
  Future<List<Map<String, dynamic>>> getOllamaModels(String ollamaUrl) async {
    final response = await _post(
      AppConstants.whisperOllamaModelsEndpoint,
      data: {'url': ollamaUrl},
    );

    if (response.data['success'] == true) {
      return List<Map<String, dynamic>>.from(response.data['models'] ?? []);
    } else {
      throw Exception(response.data['error'] ?? 'Failed to fetch models');
    }
  }

  /// Test Ollama connection
  Future<Map<String, dynamic>> testOllamaConnection(String url, String model) async {
    final response = await _post(
      AppConstants.whisperTestOllamaEndpoint,
      data: {
        'url': url,
        'model': model,
      },
    );
    return response.data;
  }

  /// Get export URL for transcript (Word or PDF)
  String getExportTranscriptUrl(int transcriptionId, String format) {
    return '$_baseUrl${AppConstants.whisperExportTranscriptEndpoint}/$transcriptionId/$format';
  }

  /// Get export URL for AI content (Word or PDF)
  String getExportAIContentUrl(int transcriptionId, String generationType, String format) {
    return '$_baseUrl${AppConstants.whisperExportAIContentEndpoint}/$transcriptionId/$generationType/$format';
  }

  // Handle Dio errors
  Exception _handleError(DioError error) {
    String userMessage;
    if (error.type == DioErrorType.connectTimeout ||
        error.type == DioErrorType.sendTimeout ||
        error.type == DioErrorType.receiveTimeout) {
      userMessage = 'Connection timeout. Please check your network connection.';
    } else if (error.type == DioErrorType.response) {
      final statusCode = error.response?.statusCode;
      final message = error.response?.data?['error'] ?? 'Server error';
      userMessage = 'Whisper service error ($statusCode): $message';
    } else if (error.type == DioErrorType.cancel) {
      userMessage = 'Request was cancelled';
    } else if (error.type == DioErrorType.other) {
      if (error.message.contains('SocketException')) {
        userMessage = 'Unable to connect to Whisper service. Please check the server URL and network connection.';
      } else {
        userMessage = 'Network error: ${error.message}';
      }
    } else {
      userMessage = 'An unexpected error occurred: ${error.message}';
    }

    _loggingService.error('Whisper Service Error: $userMessage',
                        screen: 'WhisperService',
                        data: {
                          'errorType': error.type.toString(),
                          'statusCode': error.response?.statusCode,
                          'requestPath': error.requestOptions.path,
                          'baseUrl': _baseUrl,
                        });

    return Exception(userMessage);
  }
}
