import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../models/conversation.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class ConversationsScreen extends StatefulWidget {
  const ConversationsScreen({Key? key}) : super(key: key);

  @override
  State<ConversationsScreen> createState() => _ConversationsScreenState();
}

class _ConversationsScreenState extends State<ConversationsScreen> {
  List<Conversation> _conversations = [];
  bool _isLoading = true;
  String? _errorMessage;
  int _limit = 100;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('ConversationsScreen', 'initState');
    
    _loadConversations();
  }

  Future<void> _loadConversations() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final response = await apiService.get(
        AppConstants.conversationsEndpoint,
        queryParameters: {'limit': _limit},
      );

      final conversations = (response.data['conversations'] as List)
          .map((json) => Conversation.fromJson(Map<String, dynamic>.from(json)))
          .toList();

      setState(() {
        _conversations = conversations;
        _isLoading = false;
      });
      
      loggingService.info('Conversations loaded successfully', screen: 'ConversationsScreen', data: {
        'count': conversations.length,
        'limit': _limit,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'ConversationsScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load conversations: ${e.toString()}';
      });
    }
  }

  Future<void> _resetConversations() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset Conversations'),
        content: const Text(
          'Are you sure you want to delete all conversation history? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(primary: AppTheme.errorColor),
            child: const Text('Reset'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final apiService = Provider.of<ApiService>(context, listen: false);
        final loggingService = Provider.of<LoggingService>(context, listen: false);
        
        loggingService.logUserAction('Reset Conversations', screen: 'ConversationsScreen');
        
        await apiService.post(AppConstants.conversationsEndpoint + '/reset');
        
        setState(() {
          _conversations.clear();
        });

        loggingService.info('Conversations reset successfully', screen: 'ConversationsScreen');

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Conversations reset successfully'),
              backgroundColor: AppTheme.successColor,
            ),
          );
        }
      } catch (e, stackTrace) {
        final loggingService = Provider.of<LoggingService>(context, listen: false);
        loggingService.logException(e, stackTrace, screen: 'ConversationsScreen');
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to reset conversations: ${e.toString()}'),
              backgroundColor: AppTheme.errorColor,
            ),
          );
        }
      }
    }
  }

  void _copyMessage(String message) {
    // TODO: Implement clipboard functionality
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Copy functionality not implemented yet'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  String _formatTimestamp(String? timestamp) {
    if (timestamp == null) return '';
    try {
      final date = DateTime.parse(timestamp);
      return '${date.day}/${date.month}/${date.year} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
    } catch (e) {
      return timestamp;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Conversations'),
        actions: [
          PopupMenuButton<int>(
            onSelected: (limit) {
              setState(() {
                _limit = limit;
              });
              _loadConversations();
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 50,
                child: Text('Last 50 messages'),
              ),
              const PopupMenuItem(
                value: 100,
                child: Text('Last 100 messages'),
              ),
              const PopupMenuItem(
                value: 200,
                child: Text('Last 200 messages'),
              ),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadConversations,
            tooltip: 'Refresh',
          ),
          IconButton(
            icon: const Icon(Icons.delete_forever),
            onPressed: _resetConversations,
            tooltip: 'Reset Conversations',
          ),
        ],
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading conversations...')
          : _errorMessage != null
              ? _buildErrorState()
              : _conversations.isEmpty
                  ? _buildEmptyState()
                  : RefreshIndicator(
                      onRefresh: _loadConversations,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(AppTheme.spacingM),
                        itemCount: _conversations.length,
                        itemBuilder: (context, index) {
                          final conversation = _conversations[index];
                          return _buildConversationCard(conversation);
                        },
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
              'Error Loading Conversations',
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
              onPressed: _loadConversations,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.chat_bubble_outline,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'No Conversations',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Start chatting to see conversation history here',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppTheme.spacingL),
            ElevatedButton.icon(
              onPressed: () => Navigator.pushNamed(context, '/chat'),
              icon: const Icon(Icons.chat),
              label: const Text('Start Chatting'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConversationCard(Conversation conversation) {
    return Card(
      margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
      child: InkWell(
        onTap: () => _showMessageDetails(conversation),
        borderRadius: BorderRadius.circular(AppTheme.radiusL),
        child: Padding(
          padding: const EdgeInsets.all(AppTheme.spacingM),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 16,
                    backgroundColor: conversation.isUser 
                        ? AppTheme.textSecondary 
                        : AppTheme.primaryColor,
                    child: Icon(
                      conversation.isUser ? Icons.person : Icons.smart_toy,
                      size: 16,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingS),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          conversation.isUser ? conversation.userName : 'AI Assistant',
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          _formatTimestamp(conversation.timestamp),
                          style: AppTheme.timestampStyle,
                        ),
                      ],
                    ),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (conversation.isVoice)
                        const Icon(
                          Icons.mic,
                          size: 16,
                          color: AppTheme.primaryColor,
                        ),
                      if (conversation.isText)
                        const Icon(
                          Icons.chat,
                          size: 16,
                          color: AppTheme.textSecondary,
                        ),
                      const SizedBox(width: AppTheme.spacingS),
                      IconButton(
                        icon: const Icon(Icons.copy, size: 16),
                        onPressed: () => _copyMessage(conversation.message),
                        tooltip: 'Copy Message',
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(
                          minWidth: 24,
                          minHeight: 24,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: AppTheme.spacingS),
              Text(
                conversation.message,
                style: AppTheme.messageBubbleStyle,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showMessageDetails(Conversation conversation) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            CircleAvatar(
              radius: 16,
              backgroundColor: conversation.isUser 
                  ? AppTheme.textSecondary 
                  : AppTheme.primaryColor,
              child: Icon(
                conversation.isUser ? Icons.person : Icons.smart_toy,
                size: 16,
                color: Colors.white,
              ),
            ),
            const SizedBox(width: AppTheme.spacingS),
            Expanded(
              child: Text(
                conversation.isUser ? conversation.userName : 'AI Assistant',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _formatTimestamp(conversation.timestamp),
              style: AppTheme.timestampStyle,
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Type: ${conversation.messageType}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppTheme.spacingM),
              decoration: BoxDecoration(
                color: AppTheme.backgroundColor,
                borderRadius: BorderRadius.circular(AppTheme.radiusM),
                border: Border.all(color: AppTheme.borderColor),
              ),
              child: Text(
                conversation.message,
                style: AppTheme.messageBubbleStyle,
              ),
            ),
          ],
        ),
        actions: [
          TextButton.icon(
            onPressed: () {
              _copyMessage(conversation.message);
              Navigator.pop(context);
            },
            icon: const Icon(Icons.copy),
            label: const Text('Copy'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}
