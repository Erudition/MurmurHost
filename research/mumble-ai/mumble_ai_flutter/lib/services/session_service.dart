import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

class SessionService {
  static const String _sessionIdKey = 'chat_session_id';
  static const String _sessionStartTimeKey = 'chat_session_start_time';
  static const String _sessionMessageCountKey = 'chat_session_message_count';
  
  static SessionService? _instance;
  static SharedPreferences? _prefs;
  static const _uuid = Uuid();

  SessionService._();

  static Future<SessionService> getInstance() async {
    _instance ??= SessionService._();
    _prefs ??= await SharedPreferences.getInstance();
    return _instance!;
  }

  /// Get or create a session ID for the current chat session
  String getOrCreateSessionId() {
    final existingSessionId = _prefs?.getString(_sessionIdKey);
    if (existingSessionId != null && existingSessionId.isNotEmpty) {
      return existingSessionId;
    }
    
    // Generate new session ID
    final newSessionId = _uuid.v4();
    _prefs?.setString(_sessionIdKey, newSessionId);
    _prefs?.setInt(_sessionStartTimeKey, DateTime.now().millisecondsSinceEpoch);
    _prefs?.setInt(_sessionMessageCountKey, 0);
    
    return newSessionId;
  }

  /// Get the current session ID (may be null if no session exists)
  String? getCurrentSessionId() {
    return _prefs?.getString(_sessionIdKey);
  }

  /// Reset the current session (clear session ID and metadata)
  Future<void> resetSession() async {
    await _prefs?.remove(_sessionIdKey);
    await _prefs?.remove(_sessionStartTimeKey);
    await _prefs?.remove(_sessionMessageCountKey);
  }

  /// Save session metadata
  Future<void> saveSession(String sessionId) async {
    await _prefs?.setString(_sessionIdKey, sessionId);
    await _prefs?.setInt(_sessionStartTimeKey, DateTime.now().millisecondsSinceEpoch);
  }

  /// Load existing session ID
  Future<String?> loadSession() async {
    return _prefs?.getString(_sessionIdKey);
  }

  /// Increment message count for current session
  Future<void> incrementMessageCount() async {
    final currentCount = _prefs?.getInt(_sessionMessageCountKey) ?? 0;
    await _prefs?.setInt(_sessionMessageCountKey, currentCount + 1);
  }

  /// Get session metadata
  Map<String, dynamic> getSessionMetadata() {
    final sessionId = _prefs?.getString(_sessionIdKey);
    final startTime = _prefs?.getInt(_sessionStartTimeKey);
    final messageCount = _prefs?.getInt(_sessionMessageCountKey) ?? 0;
    
    return {
      'session_id': sessionId,
      'start_time': startTime != null ? DateTime.fromMillisecondsSinceEpoch(startTime) : null,
      'message_count': messageCount,
      'duration_minutes': startTime != null 
          ? DateTime.now().difference(DateTime.fromMillisecondsSinceEpoch(startTime)).inMinutes
          : 0,
    };
  }

  /// Check if a session is active
  bool hasActiveSession() {
    final sessionId = _prefs?.getString(_sessionIdKey);
    return sessionId != null && sessionId.isNotEmpty;
  }
}
