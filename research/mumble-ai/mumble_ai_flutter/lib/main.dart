import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'utils/theme.dart';
import 'utils/constants.dart';
import 'services/storage_service.dart';
import 'services/api_service.dart';
import 'services/audio_service.dart';
import 'services/logging_service.dart';
import 'services/session_service.dart';
import 'services/whisper_service.dart';
import 'screens/server_connect_screen.dart';
import 'screens/user_selection_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/ai_chat_screen.dart';
import 'screens/conversations_screen.dart';
import 'screens/memories_screen.dart';
import 'screens/schedule_screen.dart';
import 'screens/voice_config_screen.dart';
import 'screens/ollama_config_screen.dart';
import 'screens/email_settings_screen.dart';
import 'screens/email_logs_screen.dart';
import 'screens/persona_screen.dart';
import 'screens/advanced_settings_screen.dart';
import 'screens/whisper_language_screen.dart';
import 'screens/memory_system_screen.dart';
import 'screens/transcriptions_screen.dart';
import 'screens/transcription_detail_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Set up global error handling
  FlutterError.onError = (FlutterErrorDetails details) {
    final loggingService = LoggingService.getInstance();
    loggingService.logException(
      details.exception,
      details.stack,
      screen: 'GlobalErrorHandler',
    );
    
    // Also print to console for development
    if (kDebugMode) {
      FlutterError.presentError(details);
    }
  };

  // Note: Platform error handling removed due to compatibility issues
  // Global Flutter error handling is still active
  
  // Initialize services
  final storageService = await StorageService.getInstance();
  final apiService = ApiService.getInstance();
  final audioService = AudioService.getInstance();
  final loggingService = LoggingService.getInstance();
  final sessionService = await SessionService.getInstance();
  final whisperService = WhisperService.getInstance();
  
  // Set ApiService reference for automatic log sending
  loggingService.setApiService(apiService);
  
  // Load logs from storage
  await loggingService.loadLogsFromStorage();
  
  // Log app startup
  loggingService.info('App started', screen: 'main');
  
  runApp(MyApp(
    storageService: storageService,
    apiService: apiService,
    audioService: audioService,
    loggingService: loggingService,
    sessionService: sessionService,
    whisperService: whisperService,
  ));
}

class MyApp extends StatelessWidget {
  final StorageService storageService;
  final ApiService apiService;
  final AudioService audioService;
  final LoggingService loggingService;
  final SessionService sessionService;
  final WhisperService whisperService;

  const MyApp({
    Key? key,
    required this.storageService,
    required this.apiService,
    required this.audioService,
    required this.loggingService,
    required this.sessionService,
    required this.whisperService,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<StorageService>.value(value: storageService),
        Provider<ApiService>.value(value: apiService),
        Provider<AudioService>.value(value: audioService),
        Provider<LoggingService>.value(value: loggingService),
        Provider<SessionService>.value(value: sessionService),
        Provider<WhisperService>.value(value: whisperService),
      ],
      child: MaterialApp(
        title: AppConstants.appName,
        theme: AppTheme.lightTheme,
        home: const ServerConnectScreen(),
                routes: {
                  '/connect': (context) => const ServerConnectScreen(),
                  '/user-selection': (context) => const UserSelectionScreen(),
                  '/dashboard': (context) => const DashboardScreen(),
                  '/chat': (context) => const AiChatScreen(),
                  '/conversations': (context) => const ConversationsScreen(),
                  '/memories': (context) => const MemoriesScreen(),
                  '/schedule': (context) => const ScheduleScreen(),
                  '/voice-config': (context) => const VoiceConfigScreen(),
                  '/ollama-config': (context) => const OllamaConfigScreen(),
                  '/email-settings': (context) => const EmailSettingsScreen(),
                  '/email-logs': (context) => const EmailLogsScreen(),
                  '/persona': (context) => const PersonaScreen(),
                  '/advanced-settings': (context) => const AdvancedSettingsScreen(),
                  '/whisper-language': (context) => const WhisperLanguageScreen(),
                  '/memory-system': (context) => const MemorySystemScreen(),
                  '/transcriptions': (context) => const TranscriptionsScreen(),
                  '/transcription-detail': (context) => const TranscriptionDetailScreen(),
                },
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}