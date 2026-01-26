class AppConstants {
  // App Info
  static const String appName = 'Mumble AI Control Panel';
  static const String appVersion = '1.0.0';
  
  // API Response Field Names (as returned by web-control-panel)
  // Note: host.docker.internal URLs are automatically transformed to use server IP
  //
  // /api/ollama/config GET: {url: string, model: string}
  // /api/ollama/vision_config GET: {vision_model: string}
  // /api/ollama/memory_model_config GET: {memory_extraction_model: string}
  // /api/piper/current GET: {voice: string}
  // /api/silero/current GET: {voice: string}
  // /api/chatterbox/current GET: {voice: string}
  
  // API Endpoints
  static const String healthEndpoint = '/api/stats';
  static const String statsEndpoint = '/api/stats';
  static const String conversationsEndpoint = '/api/conversations';
  static const String memoriesEndpoint = '/api/memories';
  static const String scheduleEndpoint = '/api/schedule';
  static const String emailSettingsEndpoint = '/api/email/settings';
  static const String emailLogsEndpoint = '/api/email/logs';
  static const String emailMappingsEndpoint = '/api/email/mappings';
  static const String ollamaConfigEndpoint = '/api/ollama/config';
  static const String ollamaModelsEndpoint = '/api/ollama/models';
  static const String visionConfigEndpoint = '/api/ollama/vision_config';
  static const String visionModelsEndpoint = '/api/ollama/vision_models';
  static const String memoryModelConfigEndpoint = '/api/ollama/memory_model_config';
  static const String ttsEngineEndpoint = '/api/tts/engine';
  static const String piperVoicesEndpoint = '/api/piper/voices';
  static const String piperCurrentEndpoint = '/api/piper/current';
  static const String piperPreviewEndpoint = '/api/piper/preview';
  static const String sileroVoicesEndpoint = '/api/silero/voices';
  static const String sileroCurrentEndpoint = '/api/silero/current';
  static const String sileroPreviewEndpoint = '/api/silero/preview';
  static const String chatterboxVoicesEndpoint = '/api/chatterbox/voices';
  static const String chatterboxCurrentEndpoint = '/api/chatterbox/current';
  static const String chatterboxPreviewEndpoint = '/api/chatterbox/preview';
  static const String personaEndpoint = '/api/persona';
  static const String personaEnhanceEndpoint = '/api/persona/enhance';
  static const String whisperLanguageEndpoint = '/api/whisper/language';
  static const String advancedSettingsEndpoint = '/api/advanced-settings';
  static const String usersEndpoint = '/api/users';
  static const String scheduleUsersEndpoint = '/api/schedule/users';
  static const String upcomingEventsEndpoint = '/api/schedule/upcoming';
  static const String testEmailEndpoint = '/api/email/test';
  static const String generateSignatureEndpoint = '/api/email/generate-signature';
  static const String retryEmailEndpoint = '/api/email/retry';
  static const String chatEndpoint = '/api/chat';

  // Memory System API Endpoints
  static const String memoryStatusEndpoint = '/api/memory/status';
  static const String memoryEntitiesEndpoint = '/api/memory/entities';
  static const String memorySearchEndpoint = '/api/memory/search';
  static const String memoryConsolidationEndpoint = '/api/memory/consolidation';
  static const String memoryConsolidationRunEndpoint = '/api/memory/consolidation/run';
  static const String memoryContextEndpoint = '/api/memory/context';
  static const String memoryStatsEndpoint = '/api/memory/stats';

  // Whisper Web Transcription Service (port 5008)
  static const int whisperPort = 5008;
  static const String whisperTranscriptionsEndpoint = '/api/transcriptions';
  static const String whisperUploadEndpoint = '/api/upload';
  static const String whisperTranscribeEndpoint = '/api/transcribe';
  static const String whisperSummarizeEndpoint = '/api/summarize';
  static const String whisperRegenerateTitleEndpoint = '/api/regenerate-title';
  static const String whisperGenerateAIContentEndpoint = '/api/generate-ai-content';
  static const String whisperGetAIContentEndpoint = '/api/get-ai-content';
  static const String whisperExportTranscriptEndpoint = '/api/export-transcript';
  static const String whisperExportAIContentEndpoint = '/api/export-ai-content';
  static const String whisperSpeakersEndpoint = '/api/speakers';
  static const String whisperSettingsEndpoint = '/api/settings';
  static const String whisperTestOllamaEndpoint = '/api/settings/test-ollama';
  static const String whisperOllamaModelsEndpoint = '/api/settings/ollama-models';

  // Whisper AI Generation Types
  static const List<String> whisperAIGenerationTypes = [
    'brief_summary',
    'detailed_summary',
    'action_items',
    'key_points',
    'meeting_notes',
    'sop',
    'technical_doc',
    'executive_summary',
    'qa',
    'sentiment',
    'timeline',
    'keywords',
    'transcript_summary',
    'custom',
  ];

  // Whisper AI Generation Type Display Names
  static const Map<String, String> whisperAIGenerationTypeDisplayNames = {
    'brief_summary': 'Brief Summary',
    'detailed_summary': 'Detailed Summary',
    'action_items': 'Action Items',
    'key_points': 'Key Points',
    'meeting_notes': 'Meeting Notes',
    'sop': 'Standard Operating Procedure',
    'technical_doc': 'Technical Documentation',
    'executive_summary': 'Executive Summary',
    'qa': 'Q&A Format',
    'sentiment': 'Sentiment Analysis',
    'timeline': 'Timeline',
    'keywords': 'Keywords',
    'transcript_summary': 'Transcript Summary',
    'custom': 'Custom',
  };

  // Entity Types
  static const List<String> entityTypes = [
    'PERSON',
    'PLACE',
    'ORGANIZATION',
    'DATE',
    'TIME',
    'EVENT',
    'OTHER',
  ];

  // Entity Type Display Names
  static const Map<String, String> entityTypeDisplayNames = {
    'PERSON': 'Person',
    'PLACE': 'Place',
    'ORGANIZATION': 'Organization',
    'DATE': 'Date',
    'TIME': 'Time',
    'EVENT': 'Event',
    'OTHER': 'Other',
  };

  // Search Types
  static const List<String> searchTypes = [
    'conversations',
    'entities',
    'all',
  ];

  // Search Type Display Names
  static const Map<String, String> searchTypeDisplayNames = {
    'conversations': 'Conversations',
    'entities': 'Entities',
    'all': 'All',
  };

  // Default Values
  static const String defaultServerUrl = 'http://192.168.1.100:5002';
  static const int defaultTimeout = 10000; // 10 seconds
  static const int chatTimeout = 300000; // 5 minutes for AI chat requests
  static const int defaultPageSize = 50;
  static const int maxPageSize = 200;

  // Memory Categories
  static const List<String> memoryCategories = [
    'preference',
    'fact',
    'schedule',
    'task',
    'other',
  ];

  // Memory Category Display Names
  static const Map<String, String> memoryCategoryDisplayNames = {
    'preference': 'Preference',
    'fact': 'Fact',
    'schedule': 'Schedule',
    'task': 'Task',
    'other': 'Other',
  };

  // TTS Engines
  static const List<String> ttsEngines = [
    'piper',
    'silero',
    'chatterbox',
  ];

  // TTS Engine Display Names
  static const Map<String, String> ttsEngineDisplayNames = {
    'piper': 'Piper TTS (CPU)',
    'silero': 'Silero TTS (GPU)',
    'chatterbox': 'Chatterbox TTS (Voice Cloning)',
  };

  // Email Types
  static const List<String> emailTypes = [
    'reply',
    'summary',
    'test',
    'other',
  ];

  // Email Directions
  static const List<String> emailDirections = [
    'sent',
    'received',
  ];

  // Email Statuses
  static const List<String> emailStatuses = [
    'success',
    'error',
  ];

  // Reminder Minutes Options
  static const List<int> reminderMinutesOptions = [
    15,
    30,
    60,
    120,
    240,
  ];

  // Reminder Minutes Display Names
  static const Map<int, String> reminderMinutesDisplayNames = {
    15: '15 minutes before',
    30: '30 minutes before',
    60: '1 hour before',
    120: '2 hours before',
    240: '4 hours before',
  };

  // Whisper Languages
  static const List<String> whisperLanguages = [
    'auto',
    'en',
    'es',
    'fr',
    'de',
    'it',
    'pt',
    'ru',
    'ja',
    'ko',
    'zh',
  ];

  // Whisper Language Display Names
  static const Map<String, String> whisperLanguageDisplayNames = {
    'auto': 'Auto-detect',
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh': 'Chinese',
  };

  // Timezones
  static const List<String> timezones = [
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'Europe/London',
    'Europe/Paris',
    'Europe/Berlin',
    'Asia/Tokyo',
    'Asia/Shanghai',
    'Australia/Sydney',
  ];

  // Timezone Display Names
  static const Map<String, String> timezoneDisplayNames = {
    'America/New_York': 'Eastern Time (ET)',
    'America/Chicago': 'Central Time (CT)',
    'America/Denver': 'Mountain Time (MT)',
    'America/Los_Angeles': 'Pacific Time (PT)',
    'Europe/London': 'Greenwich Mean Time (GMT)',
    'Europe/Paris': 'Central European Time (CET)',
    'Europe/Berlin': 'Central European Time (CET)',
    'Asia/Tokyo': 'Japan Standard Time (JST)',
    'Asia/Shanghai': 'China Standard Time (CST)',
    'Australia/Sydney': 'Australian Eastern Time (AET)',
  };
}
