import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class PersonaScreen extends StatefulWidget {
  const PersonaScreen({Key? key}) : super(key: key);

  @override
  State<PersonaScreen> createState() => _PersonaScreenState();
}

class _PersonaScreenState extends State<PersonaScreen> {
  final _personaController = TextEditingController();
  final _enhancedPersonaController = TextEditingController();
  
  bool _isLoading = true;
  bool _isSaving = false;
  bool _isEnhancing = false;
  bool _showEnhanced = false;
  String? _errorMessage;
  int _characterCount = 0;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('PersonaScreen', 'initState');
    
    _loadPersona();
    _personaController.addListener(_updateCharacterCount);
  }

  @override
  void dispose() {
    _personaController.dispose();
    _enhancedPersonaController.dispose();
    super.dispose();
  }

  void _updateCharacterCount() {
    setState(() {
      _characterCount = _personaController.text.length;
    });
  }

  Future<void> _loadPersona() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final response = await apiService.get(AppConstants.personaEndpoint);
      
      setState(() {
        _personaController.text = response.data['persona'] ?? '';
        _characterCount = _personaController.text.length;
        _isLoading = false;
      });
      
      loggingService.info('Persona loaded successfully', screen: 'PersonaScreen', data: {
        'characterCount': _characterCount,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'PersonaScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load persona: ${e.toString()}';
      });
    }
  }

  Future<void> _savePersona() async {
    if (_personaController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter a persona description'),
          backgroundColor: AppTheme.errorColor,
        ),
      );
      return;
    }

    setState(() {
      _isSaving = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Save Persona', screen: 'PersonaScreen', data: {
        'characterCount': _personaController.text.trim().length,
      });
      
      await apiService.post(AppConstants.personaEndpoint, data: {
        'persona': _personaController.text.trim(),
      });

      loggingService.info('Persona saved successfully', screen: 'PersonaScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Persona saved successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'PersonaScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save persona: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } finally {
      setState(() {
        _isSaving = false;
      });
    }
  }

  Future<void> _enhancePersona() async {
    if (_personaController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter a persona description first'),
          backgroundColor: AppTheme.errorColor,
        ),
      );
      return;
    }

    setState(() {
      _isEnhancing = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Enhance Persona', screen: 'PersonaScreen', data: {
        'originalLength': _personaController.text.trim().length,
      });
      
      final response = await apiService.post(AppConstants.personaEnhanceEndpoint, data: {
        'persona': _personaController.text.trim(),
      });

      setState(() {
        _enhancedPersonaController.text = response.data['enhanced_persona'] ?? '';
        _showEnhanced = true;
      });

      loggingService.info('Persona enhanced successfully', screen: 'PersonaScreen', data: {
        'enhancedLength': _enhancedPersonaController.text.length,
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Persona enhanced successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'PersonaScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to enhance persona: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } finally {
      setState(() {
        _isEnhancing = false;
      });
    }
  }

  void _acceptEnhanced() {
    setState(() {
      _personaController.text = _enhancedPersonaController.text;
      _characterCount = _personaController.text.length;
      _showEnhanced = false;
    });
  }

  void _rejectEnhanced() {
    setState(() {
      _showEnhanced = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Persona Management'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadPersona,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading persona...')
          : _errorMessage != null
              ? _buildErrorState()
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(AppTheme.spacingM),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildPersonaEditor(),
                      const SizedBox(height: AppTheme.spacingL),
                      _buildActionButtons(),
                      if (_showEnhanced) ...[
                        const SizedBox(height: AppTheme.spacingL),
                        _buildEnhancedPersona(),
                      ],
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
              'Error Loading Persona',
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
              onPressed: _loadPersona,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPersonaEditor() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'AI Persona',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                Text(
                  '$_characterCount characters',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Define the personality, behavior, and characteristics of your AI assistant. This will influence how the AI responds to users.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            TextFormField(
              controller: _personaController,
              decoration: const InputDecoration(
                labelText: 'Persona Description',
                hintText: 'Enter a detailed description of your AI assistant\'s personality...',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
              maxLines: 15,
              maxLength: 2000,
              onChanged: (value) {
                _updateCharacterCount();
              },
            ),
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
                    Icons.lightbulb_outline,
                    color: AppTheme.infoColor,
                    size: 20,
                  ),
                  const SizedBox(width: AppTheme.spacingS),
                  Expanded(
                    child: Text(
                      'Tip: Be specific about the AI\'s role, communication style, expertise areas, and any special behaviors you want it to exhibit.',
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

  Widget _buildActionButtons() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          children: [
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isEnhancing ? null : _enhancePersona,
                icon: _isEnhancing
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.auto_awesome),
                label: const Text('Enhance with AI'),
                style: ElevatedButton.styleFrom(
                  primary: AppTheme.infoColor,
                ),
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isSaving ? null : _savePersona,
                icon: _isSaving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save),
                label: const Text('Save Persona'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEnhancedPersona() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.auto_awesome,
                  color: AppTheme.infoColor,
                  size: 20,
                ),
                const SizedBox(width: AppTheme.spacingS),
                Text(
                  'AI Enhanced Persona',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: AppTheme.infoColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'The AI has enhanced your persona. Review the changes and choose to accept or reject them.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Container(
              padding: const EdgeInsets.all(AppTheme.spacingM),
              decoration: BoxDecoration(
                color: AppTheme.infoColor.withOpacity(0.05),
                borderRadius: BorderRadius.circular(AppTheme.radiusM),
                border: Border.all(
                  color: AppTheme.infoColor.withOpacity(0.2),
                ),
              ),
              child: Text(
                _enhancedPersonaController.text,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _rejectEnhanced,
                    icon: const Icon(Icons.close),
                    label: const Text('Reject'),
                    style: OutlinedButton.styleFrom(
                      primary: AppTheme.errorColor,
                      side: const BorderSide(color: AppTheme.errorColor),
                    ),
                  ),
                ),
                const SizedBox(width: AppTheme.spacingM),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _acceptEnhanced,
                    icon: const Icon(Icons.check),
                    label: const Text('Accept'),
                    style: ElevatedButton.styleFrom(
                      primary: AppTheme.successColor,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
