import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../services/session_service.dart';
import '../services/logging_service.dart';
import '../widgets/message_bubble.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class ChatMessage {
  final String message;
  final bool isUser;
  final DateTime timestamp;
  final Map<String, dynamic>? contextUsed;

  ChatMessage({
    required this.message,
    required this.isUser,
    required this.timestamp,
    this.contextUsed,
  });
}

class AiChatScreen extends StatefulWidget {
  const AiChatScreen({Key? key}) : super(key: key);

  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final _messageController = TextEditingController();
  final _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _isLoading = false;
  String? _errorMessage;
  String? _currentUser;
  String? _sessionId;
  bool _includeMemories = true;
  bool _includeSchedule = true;
  Map<String, dynamic>? _lastContextUsed;

  @override
  void initState() {
    super.initState();
    _loadUserAndSession();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('AiChatScreen', 'initState');
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadUserAndSession() async {
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    final startTime = DateTime.now();
    
    try {
      final storageService = Provider.of<StorageService>(context, listen: false);
      final sessionService = Provider.of<SessionService>(context, listen: false);
      
      // Load current user
      final user = await storageService.getSelectedUser();
      if (user == null) {
        setState(() {
          _errorMessage = 'No user selected. Please select a user first.';
        });
        return;
      }
      
      // Get or create session ID
      final sessionId = sessionService.getOrCreateSessionId();
      
      setState(() {
        _currentUser = user;
        _sessionId = sessionId;
      });
      
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Load User and Session', duration, screen: 'AiChatScreen');
      loggingService.info('User and session loaded successfully', screen: 'AiChatScreen', data: {
        'user': user,
        'sessionId': sessionId,
      });
    } catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Load User and Session (ERROR)', duration, screen: 'AiChatScreen');
      loggingService.logException(e, null, screen: 'AiChatScreen');
      
      setState(() {
        _errorMessage = 'Failed to load user information: ${e.toString()}';
      });
    }
  }

  Future<void> _sendMessage() async {
    final message = _messageController.text.trim();
    if (message.isEmpty || _isLoading || _currentUser == null) return;

    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logUserAction('Send AI Chat Message', screen: 'AiChatScreen', data: {
      'messageLength': message.length,
      'includeMemories': _includeMemories,
      'includeSchedule': _includeSchedule,
      'sessionId': _sessionId,
    });

    // Add user message
    final userMessage = ChatMessage(
      message: message,
      isUser: true,
      timestamp: DateTime.now(),
    );
    
    setState(() {
      _messages.add(userMessage);
      _isLoading = true;
      _errorMessage = null;
    });

    _messageController.clear();
    _scrollToBottom();

    try {
      // Send message to Mumble AI API
      final response = await _sendToMumbleAI(message);
      
      // Add AI response
      final aiMessage = ChatMessage(
        message: response['response'],
        isUser: false,
        timestamp: DateTime.now(),
        contextUsed: response['context_used'],
      );
      
      setState(() {
        _messages.add(aiMessage);
        _isLoading = false;
        _lastContextUsed = response['context_used'];
      });
      
      // Increment message count in session
      final sessionService = Provider.of<SessionService>(context, listen: false);
      await sessionService.incrementMessageCount();
      
      loggingService.info('AI Chat response received', screen: 'AiChatScreen', data: {
        'responseLength': response['response'].length,
        'totalMessages': _messages.length,
        'contextUsed': response['context_used'],
      });
      
      _scrollToBottom();
    } catch (e) {
      loggingService.logException(e, null, screen: 'AiChatScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to get AI response: ${e.toString()}';
      });
    }
  }

  Future<Map<String, dynamic>> _sendToMumbleAI(String message) async {
    if (_currentUser == null) {
      throw Exception('No user selected');
    }

    final loggingService = Provider.of<LoggingService>(context, listen: false);
    final startTime = DateTime.now();

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      
      loggingService.info('Sending message to Mumble AI API', screen: 'AiChatScreen', data: {
        'user': _currentUser,
        'sessionId': _sessionId,
        'includeMemories': _includeMemories,
        'includeSchedule': _includeSchedule,
        'messageLength': message.length,
      });

      final response = await apiService.postChat(AppConstants.chatEndpoint, data: {
        'user_name': _currentUser,
        'message': message,
        'session_id': _sessionId,
        'include_memories': _includeMemories,
        'include_schedule': _includeSchedule,
      });

      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Mumble AI API Call', duration, screen: 'AiChatScreen', data: {
        'responseLength': response.data['data']['response']?.toString().length ?? 0,
        'contextUsed': response.data['data']['context_used'],
      });

      // Parse the response
      final responseData = response.data;
      if (responseData['success'] == true && responseData['data'] != null) {
        return responseData['data'];
      } else {
        throw Exception('Invalid response format from server');
      }
    } catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Mumble AI API Call (ERROR)', duration, screen: 'AiChatScreen');
      loggingService.logException(e, null, screen: 'AiChatScreen');
      
      throw Exception('Mumble AI API error: ${e.toString()}');
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance?.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
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

  void _clearChat() {
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear Chat'),
        content: const Text('Are you sure you want to clear all messages? This will also reset your session.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () async {
              loggingService.logUserAction('Clear Chat', screen: 'AiChatScreen', data: {
                'messageCount': _messages.length,
              });
              
              // Reset session
              final sessionService = Provider.of<SessionService>(context, listen: false);
              await sessionService.resetSession();
              
              // Reload session
              await _loadUserAndSession();
              
              setState(() {
                _messages.clear();
                _lastContextUsed = null;
              });
              Navigator.pop(context);
            },
            child: const Text('Clear'),
          ),
        ],
      ),
    );
  }

  String _formatTimestamp(DateTime timestamp) {
    return '${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}';
  }

  Widget _buildContextIndicator() {
    if (_lastContextUsed == null) return const SizedBox.shrink();
    
    final memoriesCount = _lastContextUsed!['memories_count'] ?? 0;
    final scheduleCount = _lastContextUsed!['schedule_events_count'] ?? 0;
    
    if (memoriesCount == 0 && scheduleCount == 0) return const SizedBox.shrink();
    
    return Container(
      margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spacingM,
        vertical: AppTheme.spacingS,
      ),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
        border: Border.all(
          color: AppTheme.primaryColor.withOpacity(0.3),
        ),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.psychology,
            size: 16,
            color: AppTheme.primaryColor,
          ),
          const SizedBox(width: AppTheme.spacingS),
          Text(
            'Using context: ${memoriesCount} memories, ${scheduleCount} events',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.primaryColor,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildContextToggles() {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spacingM,
        vertical: AppTheme.spacingS,
      ),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: const Border(
          bottom: BorderSide(color: AppTheme.borderColor),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Row(
              children: [
                const Icon(
                  Icons.psychology,
                  size: 16,
                  color: AppTheme.textSecondary,
                ),
                const SizedBox(width: AppTheme.spacingS),
                Text(
                  'Memories',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
                Switch(
                  value: _includeMemories,
                  onChanged: (value) {
                    setState(() {
                      _includeMemories = value;
                    });
                  },
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ],
            ),
          ),
          Expanded(
            child: Row(
              children: [
                const Icon(
                  Icons.calendar_today,
                  size: 16,
                  color: AppTheme.textSecondary,
                ),
                const SizedBox(width: AppTheme.spacingS),
                Text(
                  'Schedule',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
                Switch(
                  value: _includeSchedule,
                  onChanged: (value) {
                    setState(() {
                      _includeSchedule = value;
                    });
                  },
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Chat'),
        actions: [
          if (_messages.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.clear_all),
              onPressed: _clearChat,
              tooltip: 'Clear Chat',
            ),
        ],
      ),
      body: Column(
        children: [
          // Error message
          if (_errorMessage != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppTheme.spacingM),
              color: AppTheme.errorColor.withOpacity(0.1),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: AppTheme.errorColor),
                  const SizedBox(width: AppTheme.spacingS),
                  Expanded(
                    child: Text(
                      _errorMessage!,
                      style: const TextStyle(color: AppTheme.errorColor),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: AppTheme.errorColor),
                    onPressed: () {
                      setState(() {
                        _errorMessage = null;
                      });
                    },
                  ),
                ],
              ),
            ),
          
          // Context toggles
          _buildContextToggles(),
          
          // Context indicator
          _buildContextIndicator(),
          
          // Messages list
          Expanded(
            child: _messages.isEmpty
                ? Center(
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
                          'Start a conversation',
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const SizedBox(height: AppTheme.spacingS),
                        Text(
                          'Send a message to begin chatting with the AI',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: AppTheme.textTertiary,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        if (_currentUser != null) ...[
                          const SizedBox(height: AppTheme.spacingM),
                          Text(
                            'Chatting as: $_currentUser',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: AppTheme.primaryColor,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ],
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(vertical: AppTheme.spacingM),
                    itemCount: _messages.length + (_isLoading ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == _messages.length && _isLoading) {
                        return Padding(
                          padding: const EdgeInsets.all(AppTheme.spacingM),
                          child: Row(
                            children: [
                              const CircleAvatar(
                                radius: 16,
                                backgroundColor: AppTheme.primaryColor,
                                child: Icon(
                                  Icons.smart_toy,
                                  size: 16,
                                  color: Colors.white,
                                ),
                              ),
                              const SizedBox(width: AppTheme.spacingS),
                              Expanded(
                                child: Card(
                                  child: Padding(
                                    padding: const EdgeInsets.all(AppTheme.spacingM),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        const SizedBox(
                                          width: 20,
                                          height: 20,
                                          child: CircularProgressIndicator(strokeWidth: 2),
                                        ),
                                        const SizedBox(width: AppTheme.spacingS),
                                        Text(
                                          _includeMemories || _includeSchedule 
                                              ? 'AI is thinking with your context...\nThis may take up to 5 minutes for complex requests.'
                                              : 'AI is thinking...\nThis may take up to 5 minutes for complex requests.',
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        );
                      }

                      final message = _messages[index];
                      return MessageBubble(
                        message: message.message,
                        isUser: message.isUser,
                        timestamp: _formatTimestamp(message.timestamp),
                        onCopy: () => _copyMessage(message.message),
                      );
                    },
                  ),
          ),
          
          // Input area
          Container(
            padding: const EdgeInsets.all(AppTheme.spacingM),
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              border: const Border(
                top: BorderSide(color: AppTheme.borderColor),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    decoration: const InputDecoration(
                      hintText: 'Type your message...',
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: AppTheme.spacingM,
                        vertical: AppTheme.spacingS,
                      ),
                    ),
                    maxLines: null,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _sendMessage(),
                    enabled: !_isLoading && _currentUser != null,
                  ),
                ),
                const SizedBox(width: AppTheme.spacingS),
                FloatingActionButton(
                  onPressed: _isLoading || _currentUser == null ? null : _sendMessage,
                  mini: true,
                  child: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Icon(Icons.send),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}