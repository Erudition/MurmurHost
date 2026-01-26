import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/whisper_service.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../models/transcription.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class TranscriptionsScreen extends StatefulWidget {
  const TranscriptionsScreen({Key? key}) : super(key: key);

  @override
  State<TranscriptionsScreen> createState() => _TranscriptionsScreenState();
}

class _TranscriptionsScreenState extends State<TranscriptionsScreen> {
  List<Transcription> _transcriptions = [];
  bool _isLoading = true;
  String? _errorMessage;
  int _currentPage = 1;
  int _totalPages = 1;
  int _totalTranscriptions = 0;
  String _searchQuery = '';
  final int _perPage = 20;

  final TextEditingController _searchController = TextEditingController();
  final WhisperService _whisperService = WhisperService.getInstance();

  @override
  void initState() {
    super.initState();

    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('TranscriptionsScreen', 'initState');

    // Initialize Whisper service with server IP
    _initializeWhisperService();

    _loadTranscriptions();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _initializeWhisperService() {
    final apiService = Provider.of<ApiService>(context, listen: false);
    if (apiService.baseUrl != null) {
      _whisperService.setBaseUrl(apiService.baseUrl!);
    }
  }

  Future<void> _loadTranscriptions() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final result = await _whisperService.getTranscriptions(
        page: _currentPage,
        perPage: _perPage,
        search: _searchQuery.isEmpty ? null : _searchQuery,
      );

      setState(() {
        _transcriptions = result['transcriptions'] as List<Transcription>;
        _totalTranscriptions = result['total'] as int;
        _totalPages = (_totalTranscriptions / _perPage).ceil();
        _isLoading = false;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'TranscriptionsScreen');

      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load transcriptions: ${e.toString()}';
      });
    }
  }

  void _handleSearch(String query) {
    setState(() {
      _searchQuery = query;
      _currentPage = 1;
    });
    _loadTranscriptions();
  }

  void _handleDelete(int id) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Transcription'),
        content: const Text('Are you sure you want to delete this transcription? This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(primary: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await _whisperService.deleteTranscription(id);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Transcription deleted successfully')),
        );
        _loadTranscriptions();
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete: ${e.toString()}')),
        );
      }
    }
  }

  void _navigateToDetail(int id) {
    Navigator.pushNamed(
      context,
      '/transcription-detail',
      arguments: id,
    ).then((_) => _loadTranscriptions()); // Reload when returning
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Transcriptions'),
        backgroundColor: AppTheme.primaryColor,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: Column(
        children: [
          // Search bar
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.primaryColor,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.1),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: TextField(
              controller: _searchController,
              onSubmitted: _handleSearch,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Search transcriptions...',
                hintStyle: TextStyle(color: Colors.white.withOpacity(0.7)),
                prefixIcon: const Icon(Icons.search, color: Colors.white),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, color: Colors.white),
                        onPressed: () {
                          _searchController.clear();
                          _handleSearch('');
                        },
                      )
                    : null,
                filled: true,
                fillColor: Colors.white.withOpacity(0.2),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
            ),
          ),

          // Results count
          if (!_isLoading && _transcriptions.isNotEmpty)
            Container(
              padding: const EdgeInsets.all(12),
              color: Colors.grey[100],
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Found $_totalTranscriptions transcription${_totalTranscriptions != 1 ? 's' : ''}',
                    style: TextStyle(color: Colors.grey[700], fontSize: 14),
                  ),
                  Text(
                    'Page $_currentPage of $_totalPages',
                    style: TextStyle(color: Colors.grey[700], fontSize: 14),
                  ),
                ],
              ),
            ),

          // Content
          Expanded(
            child: _buildContent(),
          ),

          // Pagination
          if (!_isLoading && _totalPages > 1) _buildPagination(),
        ],
      ),
    );
  }

  Widget _buildContent() {
    if (_isLoading) {
      return const Center(child: LoadingIndicator(message: 'Loading transcriptions...'));
    }

    if (_errorMessage != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red[300]),
            const SizedBox(height: 16),
            Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadTranscriptions,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (_transcriptions.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.mic_none, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            Text(
              _searchQuery.isEmpty
                  ? 'No transcriptions yet'
                  : 'No transcriptions found for "$_searchQuery"',
              style: TextStyle(color: Colors.grey[600], fontSize: 16),
            ),
            if (_searchQuery.isNotEmpty) ...[
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  _searchController.clear();
                  _handleSearch('');
                },
                child: const Text('Clear Search'),
              ),
            ],
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadTranscriptions,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _transcriptions.length,
        itemBuilder: (context, index) {
          final transcription = _transcriptions[index];
          return _buildTranscriptionCard(transcription);
        },
      ),
    );
  }

  Widget _buildTranscriptionCard(Transcription transcription) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: () => _navigateToDetail(transcription.id),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      transcription.displayTitle,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete_outline, color: Colors.red),
                    onPressed: () => _handleDelete(transcription.id),
                    tooltip: 'Delete',
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.schedule, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(
                    transcription.formattedDuration,
                    style: TextStyle(color: Colors.grey[600], fontSize: 14),
                  ),
                  const SizedBox(width: 16),
                  if (transcription.language != null) ...[
                    Icon(Icons.language, size: 16, color: Colors.grey[600]),
                    const SizedBox(width: 4),
                    Text(
                      transcription.language!.toUpperCase(),
                      style: TextStyle(color: Colors.grey[600], fontSize: 14),
                    ),
                    const SizedBox(width: 16),
                  ],
                  Icon(Icons.calendar_today, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(
                    _formatDate(transcription.uploadDate),
                    style: TextStyle(color: Colors.grey[600], fontSize: 14),
                  ),
                ],
              ),
              if (transcription.summary != null) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.blue[50],
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.summarize, size: 16, color: Colors.blue[700]),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          transcription.summary!,
                          style: TextStyle(color: Colors.blue[900], fontSize: 13),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPagination() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 4,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          ElevatedButton.icon(
            onPressed: _currentPage > 1
                ? () {
                    setState(() => _currentPage--);
                    _loadTranscriptions();
                  }
                : null,
            icon: const Icon(Icons.chevron_left),
            label: const Text('Previous'),
          ),
          Text(
            'Page $_currentPage of $_totalPages',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          ElevatedButton.icon(
            onPressed: _currentPage < _totalPages
                ? () {
                    setState(() => _currentPage++);
                    _loadTranscriptions();
                  }
                : null,
            icon: const Icon(Icons.chevron_right),
            label: const Text('Next'),
            style: ElevatedButton.styleFrom(
              primary: AppTheme.primaryColor,
              onPrimary: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(String isoDate) {
    try {
      final date = DateTime.parse(isoDate);
      return '${date.month}/${date.day}/${date.year}';
    } catch (e) {
      return isoDate;
    }
  }
}
