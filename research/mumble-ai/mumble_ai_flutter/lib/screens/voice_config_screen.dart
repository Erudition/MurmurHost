import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../services/audio_service.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class VoiceConfigScreen extends StatefulWidget {
  const VoiceConfigScreen({Key? key}) : super(key: key);

  @override
  State<VoiceConfigScreen> createState() => _VoiceConfigScreenState();
}

class _VoiceConfigScreenState extends State<VoiceConfigScreen> {
  String _selectedEngine = 'piper';
  List<Map<String, dynamic>> _piperVoices = [];
  List<Map<String, dynamic>> _sileroVoices = [];
  List<Map<String, dynamic>> _chatterboxVoices = [];
  String? _currentPiperVoice;
  String? _currentSileroVoice;
  String? _currentChatterboxVoice;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('VoiceConfigScreen', 'initState');
    
    _loadData();
  }

  Future<void> _loadData() async {
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    final startTime = DateTime.now();
    
    loggingService.logUserAction('Load Voice Configuration', screen: 'VoiceConfigScreen');
    
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      await Future.wait([
        _loadTtsEngine(),
        _loadPiperVoices(),
        _loadSileroVoices(),
        _loadChatterboxVoices(),
        _loadCurrentVoices(),
      ]);

      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Load Voice Configuration', duration, screen: 'VoiceConfigScreen');
      loggingService.info('Voice configuration loaded successfully', screen: 'VoiceConfigScreen');

      setState(() {
        _isLoading = false;
      });
    } catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Load Voice Configuration (ERROR)', duration, screen: 'VoiceConfigScreen');
      loggingService.logException(e, null, screen: 'VoiceConfigScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load voice configuration: ${e.toString()}';
      });
    }
  }

  Future<void> _loadTtsEngine() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.ttsEngineEndpoint);
      setState(() {
        _selectedEngine = response.data['engine'] ?? 'piper';
      });
    } catch (e) {
      // Use default if API fails
      setState(() {
        _selectedEngine = 'piper';
      });
    }
  }

  Future<void> _loadPiperVoices() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.piperVoicesEndpoint);
      setState(() {
        _piperVoices = List<Map<String, dynamic>>.from(response.data['voices']);
      });
    } catch (e) {
      setState(() {
        _piperVoices = [];
      });
    }
  }

  Future<void> _loadSileroVoices() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.sileroVoicesEndpoint);
      setState(() {
        _sileroVoices = List<Map<String, dynamic>>.from(response.data['voices']);
      });
    } catch (e) {
      setState(() {
        _sileroVoices = [];
      });
    }
  }

  Future<void> _loadChatterboxVoices() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.chatterboxVoicesEndpoint);
      setState(() {
        _chatterboxVoices = List<Map<String, dynamic>>.from(response.data['voices']);
      });
    } catch (e) {
      setState(() {
        _chatterboxVoices = [];
      });
    }
  }

  Future<void> _loadCurrentVoices() async {
    try {
      // Load current voices for each engine
      await Future.wait([
        _loadCurrentPiperVoice(),
        _loadCurrentSileroVoice(),
        _loadCurrentChatterboxVoice(),
      ]);
    } catch (e) {
      // Ignore errors for current voices
    }
  }

  Future<void> _loadCurrentPiperVoice() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.piperCurrentEndpoint);
      final data = apiService.safeCastResponseData(response.data);
      if (data != null) {
        setState(() {
          _currentPiperVoice = data['voice'] ?? data['name'];
        });
      }
    } catch (e) {
      setState(() {
        _currentPiperVoice = null;
      });
    }
  }

  Future<void> _loadCurrentSileroVoice() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.sileroCurrentEndpoint);
      setState(() {
        _currentSileroVoice = response.data['voice'] ?? response.data['name'];
      });
    } catch (e) {
      setState(() {
        _currentSileroVoice = null;
      });
    }
  }

  Future<void> _loadCurrentChatterboxVoice() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.chatterboxCurrentEndpoint);
      setState(() {
        _currentChatterboxVoice = response.data['voice'] ?? response.data['name'];
      });
    } catch (e) {
      setState(() {
        _currentChatterboxVoice = null;
      });
    }
  }

  Future<void> _setTtsEngine(String engine) async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Set TTS Engine', screen: 'VoiceConfigScreen', data: {
        'engine': engine,
      });
      
      await apiService.post(AppConstants.ttsEngineEndpoint, data: {'engine': engine});
      
      setState(() {
        _selectedEngine = engine;
      });

      loggingService.info('TTS engine set successfully', screen: 'VoiceConfigScreen', data: {
        'engine': engine,
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('TTS engine set to ${AppConstants.ttsEngineDisplayNames[engine]}'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'VoiceConfigScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to set TTS engine: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  Future<void> _setPiperVoice(String voice) async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Set Piper Voice', screen: 'VoiceConfigScreen', data: {
        'voice': voice,
      });
      
      await apiService.post(AppConstants.piperCurrentEndpoint, data: {'voice': voice});
      
      setState(() {
        _currentPiperVoice = voice;
      });

      loggingService.info('Piper voice updated successfully', screen: 'VoiceConfigScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Piper voice updated successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'VoiceConfigScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to set Piper voice: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  Future<void> _setSileroVoice(String voice) async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Set Silero Voice', screen: 'VoiceConfigScreen', data: {
        'voice': voice,
      });
      
      await apiService.post(AppConstants.sileroCurrentEndpoint, data: {'voice': voice});
      
      setState(() {
        _currentSileroVoice = voice;
      });

      loggingService.info('Silero voice updated successfully', screen: 'VoiceConfigScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Silero voice updated successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'VoiceConfigScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to set Silero voice: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  Future<void> _setChatterboxVoice(String voice) async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Set Chatterbox Voice', screen: 'VoiceConfigScreen', data: {
        'voice': voice,
      });
      
      await apiService.post(AppConstants.chatterboxCurrentEndpoint, data: {'voice': voice});
      
      setState(() {
        _currentChatterboxVoice = voice;
      });

      loggingService.info('Chatterbox voice updated successfully', screen: 'VoiceConfigScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Chatterbox voice updated successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'VoiceConfigScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to set Chatterbox voice: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  Future<void> _previewVoice(String engine, String voice) async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final audioService = Provider.of<AudioService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Preview Voice', screen: 'VoiceConfigScreen', data: {
        'engine': engine,
        'voice': voice,
      });
      
      String endpoint;
      switch (engine) {
        case 'piper':
          endpoint = AppConstants.piperPreviewEndpoint;
          break;
        case 'silero':
          endpoint = AppConstants.sileroPreviewEndpoint;
          break;
        case 'chatterbox':
          endpoint = AppConstants.chatterboxPreviewEndpoint;
          break;
        default:
          throw Exception('Unknown engine: $engine');
      }

      final response = await apiService.post(endpoint, data: {'voice': voice});
      
      if (response.data is String) {
        // URL response
        await audioService.playFromUrl(response.data);
      } else if (response.data is List<int>) {
        // Byte array response
        await audioService.playFromBytes(response.data);
      }

      loggingService.info('Voice preview played successfully', screen: 'VoiceConfigScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Playing voice preview...'),
            backgroundColor: AppTheme.infoColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'VoiceConfigScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to preview voice: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Voice Configuration'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading voice configuration...')
          : _errorMessage != null
              ? _buildErrorState()
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(AppTheme.spacingM),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildTtsEngineSelection(),
                      const SizedBox(height: AppTheme.spacingL),
                      if (_selectedEngine == 'piper') _buildPiperConfig(),
                      if (_selectedEngine == 'silero') _buildSileroConfig(),
                      if (_selectedEngine == 'chatterbox') _buildChatterboxConfig(),
                    ],
                  ),
                ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: AppTheme.errorColor,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'Error Loading Voice Configuration',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              _errorMessage!,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppTheme.spacingL),
            ElevatedButton.icon(
              onPressed: _loadData,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTtsEngineSelection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'TTS Engine',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            ...AppConstants.ttsEngines.map((engine) => RadioListTile<String>(
              title: Text(AppConstants.ttsEngineDisplayNames[engine] ?? engine),
              value: engine,
              groupValue: _selectedEngine,
              onChanged: (value) {
                if (value != null) {
                  _setTtsEngine(value);
                }
              },
            )),
          ],
        ),
      ),
    );
  }

  Widget _buildPiperConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'Piper Voices',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                Text(
                  '${_piperVoices.length} voices available',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            if (_piperVoices.isEmpty)
              const Text('No Piper voices available')
            else
              ..._piperVoices.map((voice) => _buildVoiceTile(
                'piper',
                voice['name'] ?? voice['voice'] ?? 'Unknown',
                voice['language'] ?? 'Unknown',
                voice['gender'] ?? 'Unknown',
                _currentPiperVoice,
                _setPiperVoice,
                _previewVoice,
              )),
          ],
        ),
      ),
    );
  }

  Widget _buildSileroConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'Silero Voices',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                Text(
                  '${_sileroVoices.length} voices available',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            if (_sileroVoices.isEmpty)
              const Text('No Silero voices available')
            else
              ..._sileroVoices.map((voice) => _buildVoiceTile(
                'silero',
                voice['name'] ?? voice['voice'] ?? 'Unknown',
                voice['language'] ?? 'Unknown',
                voice['gender'] ?? 'Unknown',
                _currentSileroVoice,
                _setSileroVoice,
                _previewVoice,
              )),
          ],
        ),
      ),
    );
  }

  Widget _buildChatterboxConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'Chatterbox Voices',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                Text(
                  '${_chatterboxVoices.length} voices available',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            if (_chatterboxVoices.isEmpty)
              const Text('No Chatterbox voices available')
            else
              ..._chatterboxVoices.map((voice) => _buildVoiceTile(
                'chatterbox',
                voice['name'] ?? voice['voice'] ?? 'Unknown',
                voice['language'] ?? 'Unknown',
                voice['description'] ?? 'Voice Cloning',
                _currentChatterboxVoice,
                _setChatterboxVoice,
                _previewVoice,
              )),
            const SizedBox(height: AppTheme.spacingM),
            Container(
              padding: const EdgeInsets.all(AppTheme.spacingM),
              decoration: BoxDecoration(
                color: AppTheme.infoColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(AppTheme.radiusM),
                border: Border.all(
                  color: AppTheme.infoColor.withOpacity(0.3),
                ),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.info_outline,
                    color: AppTheme.infoColor,
                    size: 20,
                  ),
                  const SizedBox(width: AppTheme.spacingS),
                  Expanded(
                    child: Text(
                      'Use the TTS Voice Generator web interface to create custom voice clones.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTheme.infoColor,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVoiceTile(
    String engine,
    String name,
    String language,
    String details,
    String? currentVoice,
    Function(String) onSelect,
    Function(String, String) onPreview,
  ) {
    final isSelected = currentVoice == name;
    
    return Card(
      margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
      color: isSelected ? AppTheme.primaryColor.withOpacity(0.1) : null,
      child: ListTile(
        title: Text(
          name,
          style: TextStyle(
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
            color: isSelected ? AppTheme.primaryColor : null,
          ),
        ),
        subtitle: Text('$language • $details'),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.play_arrow),
              onPressed: () => onPreview(engine, name),
              tooltip: 'Preview',
            ),
            if (isSelected)
              const Icon(
                Icons.check_circle,
                color: AppTheme.primaryColor,
              ),
          ],
        ),
        onTap: () => onSelect(name),
      ),
    );
  }
}
