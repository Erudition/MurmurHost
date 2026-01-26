import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/whisper_service.dart';
import '../services/logging_service.dart';
import '../models/transcription_segment.dart';
import '../models/ai_content.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class TranscriptionDetailScreen extends StatefulWidget {
  const TranscriptionDetailScreen({Key? key}) : super(key: key);

  @override
  State<TranscriptionDetailScreen> createState() => _TranscriptionDetailScreenState();
}

class _TranscriptionDetailScreenState extends State<TranscriptionDetailScreen> {
  DetailedTranscription? _transcription;
  Map<String, List<AIContent>> _aiContent = {};
  bool _isLoading = true;
  bool _isGenerating = false;
  String? _errorMessage;
  String? _generatingType;

  final WhisperService _whisperService = WhisperService.getInstance();
  final Map<String, bool> _expandedSections = {};

  @override
  void initState() {
    super.initState();

    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('TranscriptionDetailScreen', 'initState');

    WidgetsBinding.instance!.addPostFrameCallback((_) {
      _loadData();
    });
  }

  Future<void> _loadData() async {
    final id = ModalRoute.of(context)?.settings.arguments as int?;
    if (id == null) {
      setState(() {
        _errorMessage = 'Invalid transcription ID';
        _isLoading = false;
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final transcription = await _whisperService.getTranscription(id);
      final aiContent = await _whisperService.getAIContent(id);

      setState(() {
        _transcription = transcription;
        _aiContent = aiContent;
        _isLoading = false;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'TranscriptionDetailScreen');

      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load transcription: ${e.toString()}';
      });
    }
  }

  Future<void> _generateAIContent(String generationType) async {
    if (_transcription == null) return;

    setState(() {
      _isGenerating = true;
      _generatingType = generationType;
    });

    try {
      // Concatenate all segment texts
      final fullText = _transcription!.segments.map((s) => s.text).join(' ');

      final content = await _whisperService.generateAIContent(
        transcriptionId: _transcription!.id,
        transcriptionText: fullText,
        generationType: generationType,
      );

      setState(() {
        if (_aiContent[generationType] == null) {
          _aiContent[generationType] = [];
        }
        _aiContent[generationType]!.add(content);
        _isGenerating = false;
        _generatingType = null;
        _expandedSections[generationType] = true;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('AI content generated successfully')),
      );
    } catch (e) {
      setState(() {
        _isGenerating = false;
        _generatingType = null;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to generate: ${e.toString()}')),
      );
    }
  }

  void _copyToClipboard(String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Copied to clipboard')),
    );
  }

  Future<void> _openExportUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open export link')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_transcription?.displayTitle ?? 'Transcription'),
        backgroundColor: AppTheme.primaryColor,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: _buildContent(),
    );
  }

  Widget _buildContent() {
    if (_isLoading) {
      return const Center(child: LoadingIndicator(message: 'Loading transcription...'));
    }

    if (_errorMessage != null || _transcription == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red[300]),
            const SizedBox(height: 16),
            Text(_errorMessage ?? 'Transcription not found', style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.arrow_back),
              label: const Text('Go Back'),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(),
          _buildExportButtons(),
          _buildTranscriptionContent(),
          _buildAIContentSection(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppTheme.primaryColor, AppTheme.primaryColor.withOpacity(0.8)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _transcription!.displayTitle,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 16,
            runSpacing: 8,
            children: [
              _buildInfoChip(Icons.schedule, _formatDuration(_transcription!.duration)),
              if (_transcription!.language != null)
                _buildInfoChip(Icons.language, _transcription!.language!.toUpperCase()),
              _buildInfoChip(Icons.calendar_today, _formatDate(_transcription!.uploadDate)),
              _buildInfoChip(Icons.text_fields, '${_transcription!.segments.length} segments'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInfoChip(IconData icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.2),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.white),
          const SizedBox(width: 6),
          Text(text, style: const TextStyle(color: Colors.white, fontSize: 14)),
        ],
      ),
    );
  }

  Widget _buildExportButtons() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Expanded(
            child: ElevatedButton.icon(
              onPressed: () => _openExportUrl(
                _whisperService.getExportTranscriptUrl(_transcription!.id, 'docx'),
              ),
              icon: const Icon(Icons.description),
              label: const Text('Export Word'),
              style: ElevatedButton.styleFrom(
                primary: Colors.green,
                onPrimary: Colors.white,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: ElevatedButton.icon(
              onPressed: () => _openExportUrl(
                _whisperService.getExportTranscriptUrl(_transcription!.id, 'pdf'),
              ),
              icon: const Icon(Icons.picture_as_pdf),
              label: const Text('Export PDF'),
              style: ElevatedButton.styleFrom(
                primary: Colors.red,
                onPrimary: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTranscriptionContent() {
    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.primaryColor,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(12),
                topRight: Radius.circular(12),
              ),
            ),
            child: const Text(
              'Transcription',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _transcription!.segments.length,
            separatorBuilder: (context, index) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final segment = _transcription!.segments[index];
              return _buildSegmentTile(segment);
            },
          ),
        ],
      ),
    );
  }

  Widget _buildSegmentTile(TranscriptionSegment segment) {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: _getSpeakerColor(segment.speaker),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  segment.speaker,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                segment.formattedTime,
                style: TextStyle(color: Colors.grey[600], fontSize: 12),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            segment.text,
            style: const TextStyle(fontSize: 15, height: 1.5),
          ),
        ],
      ),
    );
  }

  Widget _buildAIContentSection() {
    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.purple[700],
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(12),
                topRight: Radius.circular(12),
              ),
            ),
            child: const Text(
              'AI Content Generation',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: AppConstants.whisperAIGenerationTypes
                  .map((type) => _buildAIGenerationOption(type))
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAIGenerationOption(String type) {
    final isGenerated = _aiContent[type]?.isNotEmpty == true;
    final isGenerating = _isGenerating && _generatingType == type;
    final isExpanded = _expandedSections[type] ?? false;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        children: [
          ListTile(
            leading: Icon(
              isGenerated ? Icons.check_circle : Icons.auto_awesome,
              color: isGenerated ? Colors.green : Colors.grey,
            ),
            title: Text(AppConstants.whisperAIGenerationTypeDisplayNames[type] ?? type),
            trailing: isGenerating
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (isGenerated)
                        IconButton(
                          icon: Icon(isExpanded ? Icons.expand_less : Icons.expand_more),
                          onPressed: () {
                            setState(() {
                              _expandedSections[type] = !isExpanded;
                            });
                          },
                        ),
                      IconButton(
                        icon: Icon(isGenerated ? Icons.refresh : Icons.play_arrow),
                        onPressed: () => _generateAIContent(type),
                        tooltip: isGenerated ? 'Regenerate' : 'Generate',
                      ),
                    ],
                  ),
          ),
          if (isGenerated && isExpanded) _buildAIContentDisplay(type, _aiContent[type]![0]),
        ],
      ),
    );
  }

  Widget _buildAIContentDisplay(String type, AIContent content) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey[50],
        border: Border(top: BorderSide(color: Colors.grey[300]!)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SelectableText(
            content.content,
            style: const TextStyle(fontSize: 14, height: 1.6),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            children: [
              ElevatedButton.icon(
                onPressed: () => _copyToClipboard(content.content),
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy'),
                style: ElevatedButton.styleFrom(
                  primary: Colors.blue,
                  onPrimary: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
              ElevatedButton.icon(
                onPressed: () => _openExportUrl(
                  _whisperService.getExportAIContentUrl(_transcription!.id, type, 'docx'),
                ),
                icon: const Icon(Icons.description, size: 16),
                label: const Text('Word'),
                style: ElevatedButton.styleFrom(
                  primary: Colors.green,
                  onPrimary: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
              ElevatedButton.icon(
                onPressed: () => _openExportUrl(
                  _whisperService.getExportAIContentUrl(_transcription!.id, type, 'pdf'),
                ),
                icon: const Icon(Icons.picture_as_pdf, size: 16),
                label: const Text('PDF'),
                style: ElevatedButton.styleFrom(
                  primary: Colors.red,
                  onPrimary: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
            ],
          ),
          if (content.model != null) ...[
            const SizedBox(height: 8),
            Text(
              'Generated with: ${content.model}',
              style: TextStyle(color: Colors.grey[600], fontSize: 12, fontStyle: FontStyle.italic),
            ),
          ],
        ],
      ),
    );
  }

  Color _getSpeakerColor(String speaker) {
    // Generate consistent colors for speakers
    final hash = speaker.hashCode;
    final colors = [
      Colors.blue[700]!,
      Colors.purple[700]!,
      Colors.green[700]!,
      Colors.orange[700]!,
      Colors.teal[700]!,
      Colors.pink[700]!,
    ];
    return colors[hash.abs() % colors.length];
  }

  String _formatDuration(double? duration) {
    if (duration == null) return 'Unknown';
    final minutes = (duration / 60).floor();
    final seconds = (duration % 60).floor();
    return '${minutes}m ${seconds}s';
  }

  String _formatDate(String isoDate) {
    try {
      final date = DateTime.parse(isoDate);
      return '${date.month}/${date.day}/${date.year} ${date.hour}:${date.minute.toString().padLeft(2, '0')}';
    } catch (e) {
      return isoDate;
    }
  }
}
