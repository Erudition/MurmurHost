import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../services/logging_service.dart';
import '../models/entity.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class MemoryContextViewer extends StatefulWidget {
  final String? userName;
  final String? sessionId;
  final bool showTitle;
  final VoidCallback? onRefresh;

  const MemoryContextViewer({
    Key? key,
    this.userName,
    this.sessionId,
    this.showTitle = true,
    this.onRefresh,
  }) : super(key: key);

  @override
  State<MemoryContextViewer> createState() => _MemoryContextViewerState();
}

class _MemoryContextViewerState extends State<MemoryContextViewer> {
  Map<String, dynamic>? _contextData;
  bool _isLoading = false;
  String? _errorMessage;
  bool _isExpanded = false;

  @override
  void initState() {
    super.initState();
    _loadContext();
  }

  Future<void> _loadContext() async {
    if (widget.userName == null) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final contextData = await apiService.getMemoryContext(
        userName: widget.userName!,
        sessionId: widget.sessionId,
        includeEntities: true,
        includeConsolidated: true,
        limit: 10,
      );

      setState(() {
        _contextData = contextData;
        _isLoading = false;
      });

      loggingService.info('Memory context loaded', screen: 'MemoryContextViewer', data: {
        'userName': widget.userName,
        'sessionId': widget.sessionId,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoryContextViewer');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load context: ${e.toString()}';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(AppTheme.spacingS),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.showTitle) _buildHeader(),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(AppTheme.spacingM),
              child: LoadingIndicator(message: 'Loading context...'),
            )
          else if (_errorMessage != null)
            _buildErrorState()
          else if (_contextData == null)
            _buildEmptyState()
          else
            _buildContextContent(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withOpacity(0.1),
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(AppTheme.radiusL),
          topRight: Radius.circular(AppTheme.radiusL),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.psychology,
            color: AppTheme.primaryColor,
            size: 20,
          ),
          const SizedBox(width: AppTheme.spacingS),
          Text(
            'Memory Context',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: AppTheme.primaryColor,
            ),
          ),
          const Spacer(),
          IconButton(
            icon: Icon(
              _isExpanded ? Icons.expand_less : Icons.expand_more,
              color: AppTheme.primaryColor,
            ),
            onPressed: () {
              setState(() {
                _isExpanded = !_isExpanded;
              });
            },
            tooltip: _isExpanded ? 'Collapse' : 'Expand',
          ),
          IconButton(
            icon: Icon(
              Icons.refresh,
              color: AppTheme.primaryColor,
            ),
            onPressed: _loadContext,
            tooltip: 'Refresh',
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Padding(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      child: Row(
        children: [
          Icon(
            Icons.error_outline,
            color: AppTheme.errorColor,
            size: 20,
          ),
          const SizedBox(width: AppTheme.spacingS),
          Expanded(
            child: Text(
              _errorMessage!,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.errorColor,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Padding(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      child: Row(
        children: [
          Icon(
            Icons.info_outline,
            color: AppTheme.textSecondary,
            size: 20,
          ),
          const SizedBox(width: AppTheme.spacingS),
          Expanded(
            child: Text(
              'No memory context available',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildContextContent() {
    if (!_isExpanded && widget.showTitle) {
      return _buildCollapsedSummary();
    }

    return Padding(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_contextData!['memories'] != null) ...[
            _buildMemoriesSection(),
            const SizedBox(height: AppTheme.spacingM),
          ],
          if (_contextData!['entities'] != null) ...[
            _buildEntitiesSection(),
            const SizedBox(height: AppTheme.spacingM),
          ],
          if (_contextData!['consolidated_memories'] != null) ...[
            _buildConsolidatedMemoriesSection(),
            const SizedBox(height: AppTheme.spacingM),
          ],
          if (_contextData!['session_data'] != null) ...[
            _buildSessionDataSection(),
          ],
        ],
      ),
    );
  }

  Widget _buildCollapsedSummary() {
    final memories = _contextData!['memories'] as List? ?? [];
    final entities = _contextData!['entities'] as List? ?? [];
    final consolidated = _contextData!['consolidated_memories'] as List? ?? [];
    
    return Padding(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      child: Row(
        children: [
          Icon(
            Icons.psychology,
            color: AppTheme.primaryColor,
            size: 16,
          ),
          const SizedBox(width: AppTheme.spacingS),
          Text(
            '${memories.length} memories, ${entities.length} entities, ${consolidated.length} consolidated',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMemoriesSection() {
    final memories = _contextData!['memories'] as List? ?? [];
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.psychology,
              color: AppTheme.warningColor,
              size: 16,
            ),
            const SizedBox(width: AppTheme.spacingS),
            Text(
              'Recent Memories (${memories.length})',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: AppTheme.warningColor,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppTheme.spacingS),
        ...memories.take(3).map((memory) => _buildMemoryItem(memory)),
        if (memories.length > 3)
          Text(
            '... and ${memories.length - 3} more',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.textTertiary,
              fontStyle: FontStyle.italic,
            ),
          ),
      ],
    );
  }

  Widget _buildMemoryItem(Map<String, dynamic> memory) {
    return Container(
      margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
      padding: const EdgeInsets.all(AppTheme.spacingS),
      decoration: BoxDecoration(
        color: AppTheme.warningColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
        border: Border.all(
          color: AppTheme.warningColor.withOpacity(0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppTheme.spacingXS,
                  vertical: 2,
                ),
                decoration: BoxDecoration(
                  color: AppTheme.warningColor,
                  borderRadius: BorderRadius.circular(AppTheme.radiusXS),
                ),
                child: Text(
                  memory['category']?.toString().toUpperCase() ?? 'MEMORY',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const Spacer(),
              Text(
                '${memory['importance'] ?? 5}/10',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppTheme.spacingXS),
          Text(
            memory['content']?.toString() ?? '',
            style: Theme.of(context).textTheme.bodySmall,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildEntitiesSection() {
    final entities = _contextData!['entities'] as List? ?? [];
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.label,
              color: AppTheme.infoColor,
              size: 16,
            ),
            const SizedBox(width: AppTheme.spacingS),
            Text(
              'Recent Entities (${entities.length})',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: AppTheme.infoColor,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppTheme.spacingS),
        Wrap(
          spacing: AppTheme.spacingXS,
          runSpacing: AppTheme.spacingXS,
          children: entities.take(5).map((entity) => _buildEntityChip(entity)).toList(),
          if (entities.length > 5)
            Text(
              '+${entities.length - 5} more',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textTertiary,
                fontStyle: FontStyle.italic,
              ),
            ),
        ),
      ],
    );
  }

  Widget _buildEntityChip(Map<String, dynamic> entity) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spacingS,
        vertical: AppTheme.spacingXS,
      ),
      decoration: BoxDecoration(
        color: AppTheme.infoColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
        border: Border.all(
          color: AppTheme.infoColor.withOpacity(0.3),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            _getEntityIcon(entity['entity_type']?.toString()),
            size: 12,
            color: AppTheme.infoColor,
          ),
          const SizedBox(width: AppTheme.spacingXS),
          Text(
            entity['entity_text']?.toString() ?? '',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.infoColor,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConsolidatedMemoriesSection() {
    final consolidated = _contextData!['consolidated_memories'] as List? ?? [];
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.merge,
              color: AppTheme.successColor,
              size: 16,
            ),
            const SizedBox(width: AppTheme.spacingS),
            Text(
              'Consolidated Memories (${consolidated.length})',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: AppTheme.successColor,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppTheme.spacingS),
        ...consolidated.take(2).map((memory) => _buildConsolidatedMemoryItem(memory)),
        if (consolidated.length > 2)
          Text(
            '... and ${consolidated.length - 2} more',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.textTertiary,
              fontStyle: FontStyle.italic,
            ),
          ),
      ],
    );
  }

  Widget _buildConsolidatedMemoryItem(Map<String, dynamic> memory) {
    return Container(
      margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
      padding: const EdgeInsets.all(AppTheme.spacingS),
      decoration: BoxDecoration(
        color: AppTheme.successColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
        border: Border.all(
          color: AppTheme.successColor.withOpacity(0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.merge,
                size: 12,
                color: AppTheme.successColor,
              ),
              const SizedBox(width: AppTheme.spacingXS),
              Text(
                'Consolidated Summary',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTheme.successColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              if (memory['created_at'] != null)
                Text(
                  _formatTimestamp(memory['created_at'].toString()),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppTheme.spacingXS),
          Text(
            memory['content']?.toString() ?? '',
            style: Theme.of(context).textTheme.bodySmall,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildSessionDataSection() {
    final sessionData = _contextData!['session_data'] as Map<String, dynamic>? ?? {};
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.session,
              color: AppTheme.primaryColor,
              size: 16,
            ),
            const SizedBox(width: AppTheme.spacingS),
            Text(
              'Session Data',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: AppTheme.primaryColor,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppTheme.spacingS),
        Container(
          padding: const EdgeInsets.all(AppTheme.spacingS),
          decoration: BoxDecoration(
            color: AppTheme.primaryColor.withOpacity(0.1),
            borderRadius: BorderRadius.circular(AppTheme.radiusS),
            border: Border.all(
              color: AppTheme.primaryColor.withOpacity(0.3),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (sessionData['session_id'] != null)
                _buildSessionInfoItem('Session ID', sessionData['session_id'].toString()),
              if (sessionData['start_time'] != null)
                _buildSessionInfoItem('Start Time', _formatTimestamp(sessionData['start_time'].toString())),
              if (sessionData['message_count'] != null)
                _buildSessionInfoItem('Messages', sessionData['message_count'].toString()),
              if (sessionData['last_activity'] != null)
                _buildSessionInfoItem('Last Activity', _formatTimestamp(sessionData['last_activity'].toString())),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSessionInfoItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppTheme.spacingXS),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(
              '$label:',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }

  IconData _getEntityIcon(String? entityType) {
    switch (entityType?.toUpperCase()) {
      case 'PERSON':
        return Icons.person;
      case 'PLACE':
        return Icons.place;
      case 'ORGANIZATION':
        return Icons.business;
      case 'DATE':
        return Icons.calendar_today;
      case 'TIME':
        return Icons.access_time;
      case 'EVENT':
        return Icons.event;
      default:
        return Icons.label;
    }
  }

  String _formatTimestamp(String timestamp) {
    try {
      final dateTime = DateTime.parse(timestamp);
      final now = DateTime.now();
      final difference = now.difference(dateTime);

      if (difference.inDays > 0) {
        return '${difference.inDays}d ago';
      } else if (difference.inHours > 0) {
        return '${difference.inHours}h ago';
      } else if (difference.inMinutes > 0) {
        return '${difference.inMinutes}m ago';
      } else {
        return 'Just now';
      }
    } catch (e) {
      return timestamp;
    }
  }
}
