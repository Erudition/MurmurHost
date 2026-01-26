import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class OllamaConfigScreen extends StatefulWidget {
  const OllamaConfigScreen({Key? key}) : super(key: key);

  @override
  State<OllamaConfigScreen> createState() => _OllamaConfigScreenState();
}

class _OllamaConfigScreenState extends State<OllamaConfigScreen> {
  final _ollamaUrlController = TextEditingController();
  final _visionModelController = TextEditingController();
  final _memoryModelController = TextEditingController();
  
  List<String> _availableModels = [];
  List<String> _visionModels = [];
  String? _selectedModel;
  String? _selectedVisionModel;
  String? _selectedMemoryModel;
  bool _isLoading = true;
  bool _isSaving = false;
  bool _isRefreshingModels = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('OllamaConfigScreen', 'initState');
    
    _loadConfiguration();
  }

  @override
  void dispose() {
    _ollamaUrlController.dispose();
    _visionModelController.dispose();
    _memoryModelController.dispose();
    super.dispose();
  }

  Future<void> _loadConfiguration() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      await Future.wait([
        _loadOllamaConfig(),
        _loadVisionConfig(),
        _loadMemoryConfig(),
        _loadModels(),
        _loadVisionModels(),
      ]);

      setState(() {
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load configuration: ${e.toString()}';
      });
    }
  }

  Future<void> _loadOllamaConfig() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.ollamaConfigEndpoint);
      
      if (response.data != null) {
        final data = apiService.safeCastResponseData(response.data);
        if (data != null) {
          setState(() {
            _ollamaUrlController.text = data['url'] ?? '';
            _selectedModel = data['model'] ?? '';
          });
        } else {
          throw Exception('Invalid data format received from server');
        }
      } else {
        throw Exception('No data received from server');
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _ollamaUrlController.text = 'http://localhost:11434';
          _selectedModel = null;
        });
      }
      // Log error for debugging
      print('Error loading Ollama config: $e');
    }
  }

  Future<void> _loadVisionConfig() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.visionConfigEndpoint);
      
      if (response.data != null) {
        final data = apiService.safeCastResponseData(response.data);
        if (data != null) {
          setState(() {
            _selectedVisionModel = data['vision_model'] ?? '';
          });
        } else {
          throw Exception('Invalid data format received from server');
        }
      } else {
        throw Exception('No data received from server');
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _selectedVisionModel = null;
        });
      }
      print('Error loading vision config: $e');
    }
  }

  Future<void> _loadMemoryConfig() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.memoryModelConfigEndpoint);
      
      if (response.data != null) {
        final data = apiService.safeCastResponseData(response.data);
        if (data != null) {
          setState(() {
            _selectedMemoryModel = data['memory_extraction_model'] ?? '';
          });
        } else {
          throw Exception('Invalid data format received from server');
        }
      } else {
        throw Exception('No data received from server');
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _selectedMemoryModel = null;
        });
      }
      print('Error loading memory config: $e');
    }
  }

  Future<void> _loadModels() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.ollamaModelsEndpoint);
      
      // Extract 'models' key from response
      final data = apiService.safeCastResponseData(response.data);
      if (data != null && data.containsKey('models')) {
        setState(() {
          _availableModels = List<String>.from(data['models']);
        });
      } else {
        setState(() {
          _availableModels = [];
        });
      }
    } catch (e) {
      setState(() {
        _availableModels = [];
      });
    }
  }

  Future<void> _loadVisionModels() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.visionModelsEndpoint);
      
      // Extract 'models' key from response
      final data = apiService.safeCastResponseData(response.data);
      if (data != null && data.containsKey('models')) {
        setState(() {
          _visionModels = List<String>.from(data['models']);
        });
      } else {
        setState(() {
          _visionModels = [];
        });
      }
    } catch (e) {
      setState(() {
        _visionModels = [];
      });
    }
  }

  Future<void> _refreshModels() async {
    setState(() {
      _isRefreshingModels = true;
    });

    try {
      await Future.wait([
        _loadModels(),
        _loadVisionModels(),
      ]);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Models refreshed successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to refresh models: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } finally {
      setState(() {
        _isRefreshingModels = false;
      });
    }
  }

  Future<void> _saveOllamaConfig() async {
    if (_ollamaUrlController.text.trim().isEmpty) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.warning('Attempted to save Ollama config with empty URL', screen: 'OllamaConfigScreen');
      
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter Ollama URL'),
          backgroundColor: AppTheme.errorColor,
        ),
      );
      return;
    }

    final loggingService = Provider.of<LoggingService>(context, listen: false);
    final startTime = DateTime.now();
    
    loggingService.logUserAction('Save Ollama Config', screen: 'OllamaConfigScreen', data: {
      'url': _ollamaUrlController.text.trim(),
      'model': _selectedModel,
    });

    setState(() {
      _isSaving = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      await apiService.post(AppConstants.ollamaConfigEndpoint, data: {
        'url': _ollamaUrlController.text.trim(),
        'model': _selectedModel,
      });

      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Save Ollama Config', duration, screen: 'OllamaConfigScreen');
      loggingService.info('Ollama configuration saved successfully', screen: 'OllamaConfigScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Ollama configuration saved successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Save Ollama Config (ERROR)', duration, screen: 'OllamaConfigScreen');
      loggingService.logException(e, null, screen: 'OllamaConfigScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save Ollama configuration: ${e.toString()}'),
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

  Future<void> _saveVisionConfig() async {
    setState(() {
      _isSaving = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      await apiService.post(AppConstants.visionConfigEndpoint, data: {
        'vision_model': _selectedVisionModel,
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Vision model configuration saved successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save vision model configuration: ${e.toString()}'),
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

  Future<void> _saveMemoryConfig() async {
    setState(() {
      _isSaving = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      await apiService.post(AppConstants.memoryModelConfigEndpoint, data: {
        'memory_extraction_model': _selectedMemoryModel,
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Memory model configuration saved successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save memory model configuration: ${e.toString()}'),
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

  Future<void> _testConnection() async {
    if (_ollamaUrlController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter Ollama URL first'),
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
      await apiService.post(AppConstants.ollamaConfigEndpoint, data: {
        'url': _ollamaUrlController.text.trim(),
        'model': _selectedModel,
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Connection test successful'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Connection test failed: ${e.toString()}'),
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ollama Configuration'),
        actions: [
          IconButton(
            icon: _isRefreshingModels
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
            onPressed: _isRefreshingModels ? null : _refreshModels,
            tooltip: 'Refresh Models',
          ),
        ],
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading Ollama configuration...')
          : _errorMessage != null
              ? _buildErrorState()
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(AppTheme.spacingM),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildOllamaConfig(),
                      const SizedBox(height: AppTheme.spacingL),
                      _buildVisionConfig(),
                      const SizedBox(height: AppTheme.spacingL),
                      _buildMemoryConfig(),
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
              'Error Loading Configuration',
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
              onPressed: _loadConfiguration,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOllamaConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Ollama Configuration',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            TextFormField(
              controller: _ollamaUrlController,
              decoration: const InputDecoration(
                labelText: 'Ollama URL',
                hintText: 'http://localhost:11434',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.link),
              ),
              keyboardType: TextInputType.url,
            ),
            const SizedBox(height: AppTheme.spacingM),
            DropdownButtonFormField<String>(
              value: _selectedModel,
              decoration: const InputDecoration(
                labelText: 'Model',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.psychology),
              ),
              items: _availableModels.map((model) => DropdownMenuItem<String>(
                value: model,
                child: Text(model),
              )).toList(),
              onChanged: (value) {
                setState(() {
                  _selectedModel = value;
                });
              },
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isSaving ? null : _testConnection,
                    icon: _isSaving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.wifi_protected_setup),
                    label: const Text('Test Connection'),
                  ),
                ),
                const SizedBox(width: AppTheme.spacingM),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isSaving ? null : _saveOllamaConfig,
                    icon: _isSaving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.save),
                    label: const Text('Save'),
                  ),
                ),
              ],
            ),
            if (_availableModels.isEmpty) ...[
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
                        'No models available. Make sure Ollama is running and click "Refresh Models".',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppTheme.warningColor,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildVisionConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Vision Model Configuration',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Select a vision model for image analysis and understanding.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            DropdownButtonFormField<String>(
              value: _selectedVisionModel,
              decoration: const InputDecoration(
                labelText: 'Vision Model',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.visibility),
              ),
              items: _visionModels.map((model) => DropdownMenuItem<String>(
                value: model,
                child: Text(model),
              )).toList(),
              onChanged: (value) {
                setState(() {
                  _selectedVisionModel = value;
                });
              },
            ),
            const SizedBox(height: AppTheme.spacingM),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isSaving ? null : _saveVisionConfig,
                icon: _isSaving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save),
                label: const Text('Save Vision Model'),
              ),
            ),
            if (_visionModels.isEmpty) ...[
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
                        'No vision models available. Vision models are typically multi-modal models that can process both text and images.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppTheme.infoColor,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMemoryConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Memory Extraction Model Configuration',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Select a model for extracting and processing memories from conversations.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            DropdownButtonFormField<String>(
              value: _selectedMemoryModel,
              decoration: const InputDecoration(
                labelText: 'Memory Model',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.memory),
              ),
              items: _availableModels.map((model) => DropdownMenuItem<String>(
                value: model,
                child: Text(model),
              )).toList(),
              onChanged: (value) {
                setState(() {
                  _selectedMemoryModel = value;
                });
              },
            ),
            const SizedBox(height: AppTheme.spacingM),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isSaving ? null : _saveMemoryConfig,
                icon: _isSaving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save),
                label: const Text('Save Memory Model'),
              ),
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
                      'Recommended: Use a smaller, faster model for memory extraction to improve performance.',
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
}
