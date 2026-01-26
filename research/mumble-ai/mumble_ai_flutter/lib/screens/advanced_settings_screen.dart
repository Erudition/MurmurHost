import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class AdvancedSettingsScreen extends StatefulWidget {
  const AdvancedSettingsScreen({Key? key}) : super(key: key);

  @override
  State<AdvancedSettingsScreen> createState() => _AdvancedSettingsScreenState();
}

class _AdvancedSettingsScreenState extends State<AdvancedSettingsScreen> {
  final _shortTermMemoryController = TextEditingController();
  final _longTermMemoryController = TextEditingController();
  
  bool _isLoading = true;
  bool _isSaving = false;
  String? _errorMessage;
  
  // Toggle switches
  bool _useChainOfThought = false;
  bool _useSemanticMemoryRanking = false;
  bool _useResponseValidation = false;
  bool _enableParallelProcessing = false;

  // Helper method to safely parse boolean values
  bool _parseBool(dynamic value, bool defaultValue) {
    if (value == null) return defaultValue;
    if (value is bool) return value;
    if (value is String) return value.toLowerCase() == 'true';
    return defaultValue;
  }

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('AdvancedSettingsScreen', 'initState');
    
    _loadAdvancedSettings();
  }

  @override
  void dispose() {
    _shortTermMemoryController.dispose();
    _longTermMemoryController.dispose();
    super.dispose();
  }

  Future<void> _loadAdvancedSettings() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final response = await apiService.get(AppConstants.advancedSettingsEndpoint);
      final data = response.data;

      setState(() {
        _shortTermMemoryController.text = (data['short_term_memory_limit'] is int 
            ? data['short_term_memory_limit'] 
            : int.tryParse(data['short_term_memory_limit']?.toString() ?? '10') ?? 10).toString();
        _longTermMemoryController.text = (data['long_term_memory_limit'] is int 
            ? data['long_term_memory_limit'] 
            : int.tryParse(data['long_term_memory_limit']?.toString() ?? '100') ?? 100).toString();
        _useChainOfThought = _parseBool(data['use_chain_of_thought'], false);
        _useSemanticMemoryRanking = _parseBool(data['use_semantic_memory_ranking'], false);
        _useResponseValidation = _parseBool(data['use_response_validation'], false);
        _enableParallelProcessing = _parseBool(data['enable_parallel_processing'], false);
        _isLoading = false;
      });
      
      loggingService.info('Advanced settings loaded successfully', screen: 'AdvancedSettingsScreen');
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'AdvancedSettingsScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load advanced settings: ${e.toString()}';
      });
    }
  }

  Future<void> _saveAdvancedSettings() async {
    if (!_validateInputs()) return;

    setState(() {
      _isSaving = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Save Advanced Settings', screen: 'AdvancedSettingsScreen', data: {
        'chainOfThought': _useChainOfThought,
        'semanticRanking': _useSemanticMemoryRanking,
        'responseValidation': _useResponseValidation,
        'parallelProcessing': _enableParallelProcessing,
      });
      
      await apiService.post(AppConstants.advancedSettingsEndpoint, data: {
        'short_term_memory_limit': int.parse(_shortTermMemoryController.text),
        'long_term_memory_limit': int.parse(_longTermMemoryController.text),
        'use_chain_of_thought': _useChainOfThought,
        'use_semantic_memory_ranking': _useSemanticMemoryRanking,
        'use_response_validation': _useResponseValidation,
        'enable_parallel_processing': _enableParallelProcessing,
      });

      loggingService.info('Advanced settings saved successfully', screen: 'AdvancedSettingsScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Advanced settings saved successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'AdvancedSettingsScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save advanced settings: ${e.toString()}'),
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

  bool _validateInputs() {
    final shortTerm = int.tryParse(_shortTermMemoryController.text);
    final longTerm = int.tryParse(_longTermMemoryController.text);

    if (shortTerm == null || shortTerm < 1 || shortTerm > 1000) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Short-term memory limit must be between 1 and 1000'),
          backgroundColor: AppTheme.errorColor,
        ),
      );
      return false;
    }

    if (longTerm == null || longTerm < 1 || longTerm > 10000) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Long-term memory limit must be between 1 and 10000'),
          backgroundColor: AppTheme.errorColor,
        ),
      );
      return false;
    }

    if (shortTerm > longTerm) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Short-term memory limit cannot be greater than long-term limit'),
          backgroundColor: AppTheme.errorColor,
        ),
      );
      return false;
    }

    return true;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Advanced Settings'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAdvancedSettings,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading advanced settings...')
          : _errorMessage != null
              ? _buildErrorState()
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(AppTheme.spacingM),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildMemorySettings(),
                      const SizedBox(height: AppTheme.spacingL),
                      _buildProcessingSettings(),
                      const SizedBox(height: AppTheme.spacingL),
                      _buildActionButtons(),
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
              'Error Loading Advanced Settings',
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
              onPressed: _loadAdvancedSettings,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMemorySettings() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Memory Settings',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Configure how many memories the AI can access during conversations.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _shortTermMemoryController,
                    decoration: const InputDecoration(
                      labelText: 'Short-term Memory Limit',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.memory),
                      suffixText: 'memories',
                    ),
                    keyboardType: TextInputType.number,
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Required';
                      }
                      final num = int.tryParse(value);
                      if (num == null || num < 1 || num > 1000) {
                        return '1-1000';
                      }
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: AppTheme.spacingM),
                Expanded(
                  child: TextFormField(
                    controller: _longTermMemoryController,
                    decoration: const InputDecoration(
                      labelText: 'Long-term Memory Limit',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.storage),
                      suffixText: 'memories',
                    ),
                    keyboardType: TextInputType.number,
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Required';
                      }
                      final num = int.tryParse(value);
                      if (num == null || num < 1 || num > 10000) {
                        return '1-10000';
                      }
                      return null;
                    },
                  ),
                ),
              ],
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
                      'Short-term memories are recent and highly relevant. Long-term memories provide broader context. Higher limits use more processing power.',
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

  Widget _buildProcessingSettings() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Processing Settings',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Configure advanced AI processing features that affect response quality and performance.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            _buildToggleSetting(
              title: 'Use Chain of Thought',
              subtitle: 'AI will show its reasoning process step by step',
              value: _useChainOfThought,
              onChanged: (value) {
                setState(() {
                  _useChainOfThought = value;
                });
              },
              icon: Icons.psychology,
            ),
            const SizedBox(height: AppTheme.spacingM),
            _buildToggleSetting(
              title: 'Use Semantic Memory Ranking',
              subtitle: 'Prioritize memories based on semantic similarity',
              value: _useSemanticMemoryRanking,
              onChanged: (value) {
                setState(() {
                  _useSemanticMemoryRanking = value;
                });
              },
              icon: Icons.sort,
            ),
            const SizedBox(height: AppTheme.spacingM),
            _buildToggleSetting(
              title: 'Use Response Validation',
              subtitle: 'Validate AI responses before sending to users',
              value: _useResponseValidation,
              onChanged: (value) {
                setState(() {
                  _useResponseValidation = value;
                });
              },
              icon: Icons.verified,
            ),
            const SizedBox(height: AppTheme.spacingM),
            _buildToggleSetting(
              title: 'Enable Parallel Processing',
              subtitle: 'Process multiple requests simultaneously (requires more resources)',
              value: _enableParallelProcessing,
              onChanged: (value) {
                setState(() {
                  _enableParallelProcessing = value;
                });
              },
              icon: Icons.speed,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Container(
              padding: const EdgeInsets.all(AppTheme.spacingM),
              decoration: BoxDecoration(
                color: AppTheme.warningColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(AppTheme.radiusM),
                border: Border.all(
                  color: AppTheme.warningColor.withOpacity(0.3),
                ),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.warning_outlined,
                    color: AppTheme.warningColor,
                    size: 20,
                  ),
                  const SizedBox(width: AppTheme.spacingS),
                  Expanded(
                    child: Text(
                      'Advanced features may increase response time and resource usage. Monitor system performance after enabling.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTheme.warningColor,
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

  Widget _buildToggleSetting({
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
    required IconData icon,
  }) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      decoration: BoxDecoration(
        color: value ? AppTheme.primaryColor.withOpacity(0.05) : AppTheme.backgroundColor,
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        border: Border.all(
          color: value ? AppTheme.primaryColor.withOpacity(0.2) : AppTheme.borderColor,
        ),
      ),
      child: Row(
        children: [
          Icon(
            icon,
            color: value ? AppTheme.primaryColor : AppTheme.textSecondary,
            size: 24,
          ),
          const SizedBox(width: AppTheme.spacingM),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: value ? AppTheme.primaryColor : null,
                  ),
                ),
                const SizedBox(height: AppTheme.spacingXS),
                Text(
                  subtitle,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppTheme.primaryColor,
          ),
        ],
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
                onPressed: _isSaving ? null : _saveAdvancedSettings,
                icon: _isSaving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save),
                label: const Text('Save Advanced Settings'),
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _isSaving ? null : _loadAdvancedSettings,
                icon: const Icon(Icons.refresh),
                label: const Text('Reset to Defaults'),
                style: OutlinedButton.styleFrom(
                  primary: AppTheme.textSecondary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
