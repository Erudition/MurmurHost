import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/storage_service.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../models/stats.dart';
import '../models/schedule_event.dart';
import '../widgets/stat_card.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';
import 'main_scaffold.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Stats? _stats;
  List<ScheduleEvent> _upcomingEvents = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadData();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.info('Dashboard screen loaded', screen: 'DashboardScreen');
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final storageService = Provider.of<StorageService>(context, listen: false);
      
      // Load saved server URL
      final savedUrl = await storageService.getServerUrl();
      if (savedUrl != null) {
        apiService.setBaseUrl(savedUrl);
      }

      // Load stats and upcoming events in parallel
      await Future.wait([
        _loadStats(),
        _loadUpcomingEvents(),
      ]);

      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    } catch (e) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, null, screen: 'DashboardScreen');
      
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Failed to load data: ${e.toString()}';
        });
      }
    }
  }

  Future<void> _loadStats() async {
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    final startTime = DateTime.now();
    
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.statsEndpoint);
      
      if (response.data != null) {
        // Handle both Map and List responses from the API
        dynamic data = response.data;
        
        // If it's a list, take the first item (assuming it's a single stats object)
        if (data is List && data.isNotEmpty) {
          data = data.first;
        }
        
        // Now try to cast to Map
        if (data is Map<String, dynamic>) {
          final stats = Stats.fromJson(data);
          if (mounted) {
            setState(() {
              _stats = stats;
            });
          }
          
          final duration = DateTime.now().difference(startTime);
          loggingService.logPerformance('Load Stats', duration, screen: 'DashboardScreen');
        } else if (data is Map) {
          // Handle Map<dynamic, dynamic> case
          final Map<String, dynamic> statsData = {};
          data.forEach((key, value) {
            statsData[key.toString()] = value;
          });
          
          final stats = Stats.fromJson(statsData);
          if (mounted) {
            setState(() {
              _stats = stats;
            });
          }
          
          final duration = DateTime.now().difference(startTime);
          loggingService.logPerformance('Load Stats', duration, screen: 'DashboardScreen');
        } else {
          throw Exception('Invalid data format received from stats endpoint. Expected Map or List, got ${data.runtimeType}');
        }
      } else {
        throw Exception('No data received from stats endpoint');
      }
    } catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Load Stats (ERROR)', duration, screen: 'DashboardScreen');
      loggingService.logException(e, null, screen: 'DashboardScreen');
      
      print('Error loading stats: $e');
      throw Exception('Failed to load statistics: $e');
    }
  }

  Future<void> _loadUpcomingEvents() async {
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    final startTime = DateTime.now();
    
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final storageService = Provider.of<StorageService>(context, listen: false);
      
      final queryParams = <String, dynamic>{
        'days': 7, 
        'limit': 5
      };
      
      // Include the selected user from storage
      final currentUser = await storageService.getSelectedUser();
      if (currentUser != null) {
        queryParams['user'] = currentUser;
      }
      
      final response = await apiService.get(
        AppConstants.upcomingEventsEndpoint,
        queryParameters: queryParams,
      );
      
      if (response.data != null) {
        // Handle both new wrapped format and legacy array format
        List<dynamic> eventsList;
        if (response.data is Map<String, dynamic>) {
          // New wrapped format: {"success": true, "data": [...]}
          final data = response.data['data'];
          if (data is List) {
            eventsList = data;
          } else {
            eventsList = [];
          }
        } else if (response.data is List) {
          // Legacy format: [...]
          eventsList = response.data as List;
        } else {
          // Unexpected format, treat as empty
          eventsList = [];
        }
        
        final events = eventsList
            .map((json) => ScheduleEvent.fromJson(json))
            .toList();
        
        if (mounted) {
          setState(() {
            _upcomingEvents = events;
          });
        }
        
        final duration = DateTime.now().difference(startTime);
        loggingService.logPerformance('Load Upcoming Events', duration, screen: 'DashboardScreen');
      } else {
        if (mounted) {
          setState(() {
            _upcomingEvents = [];
          });
        }
      }
    } catch (e) {
      final duration = DateTime.now().difference(startTime);
      loggingService.logPerformance('Load Upcoming Events (ERROR)', duration, screen: 'DashboardScreen');
      loggingService.logException(e, null, screen: 'DashboardScreen');
      
      // Don't throw error for upcoming events, just log it
      print('Error loading upcoming events: $e');
      if (mounted) {
        setState(() {
          _upcomingEvents = [];
        });
      }
    }
  }


  @override
  Widget build(BuildContext context) {
    return MainScaffold(
      title: 'Dashboard',
      actions: [
        IconButton(
          icon: const Icon(Icons.refresh),
          onPressed: () {
            final loggingService = Provider.of<LoggingService>(context, listen: false);
            loggingService.logUserAction('Refresh Dashboard', screen: 'DashboardScreen');
            _loadData();
          },
        ),
        IconButton(
          icon: const Icon(Icons.bug_report),
          onPressed: _sendLogsToServer,
          tooltip: 'Send Logs to Server',
        ),
          PopupMenuButton<String>(
            onSelected: (value) {
              switch (value) {
                case 'settings':
                  // TODO: Navigate to settings
                  break;
                case 'disconnect':
                  _disconnect();
                  break;
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'settings',
                child: ListTile(
                  leading: Icon(Icons.settings),
                  title: Text('Settings'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem(
                value: 'disconnect',
                child: ListTile(
                  leading: Icon(Icons.logout),
                  title: Text('Disconnect'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ],
          ),
        ],
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading dashboard...')
          : _errorMessage != null
              ? _buildErrorState()
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(AppTheme.spacingM),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Statistics Cards
                        Text(
                          'Statistics',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: AppTheme.spacingM),
                        GridView.count(
                          crossAxisCount: 2,
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          childAspectRatio: 1.5,
                          crossAxisSpacing: AppTheme.spacingM,
                          mainAxisSpacing: AppTheme.spacingM,
                          children: [
                            StatCard(
                              title: 'Total Messages',
                              value: _stats?.totalMessages.toString() ?? '0',
                              icon: Icons.message,
                              iconColor: AppTheme.primaryColor,
                            ),
                            StatCard(
                              title: 'Unique Users',
                              value: _stats?.uniqueUsers.toString() ?? '0',
                              icon: Icons.people,
                              iconColor: AppTheme.infoColor,
                            ),
                            StatCard(
                              title: 'Voice Messages',
                              value: _stats?.voiceMessages.toString() ?? '0',
                              icon: Icons.mic,
                              iconColor: AppTheme.successColor,
                            ),
                            StatCard(
                              title: 'Text Messages',
                              value: _stats?.textMessages.toString() ?? '0',
                              icon: Icons.chat,
                              iconColor: AppTheme.warningColor,
                            ),
                          ],
                        ),
                        const SizedBox(height: AppTheme.spacingXL),
                        
                        // Upcoming Events
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Upcoming Events',
                              style: Theme.of(context).textTheme.headlineSmall,
                            ),
                            TextButton(
                              onPressed: () {
                                // TODO: Navigate to schedule screen
                              },
                              child: const Text('View All'),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppTheme.spacingM),
                        _buildUpcomingEvents(),
                        const SizedBox(height: AppTheme.spacingXL),
                        
                        // Quick Actions
                        Text(
                          'Quick Actions',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: AppTheme.spacingM),
                        _buildQuickActions(),
                      ],
                    ),
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
              'Connection Error',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              _errorMessage ?? 'Unknown error occurred',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppTheme.spacingL),
            ElevatedButton.icon(
              onPressed: () {
                final loggingService = Provider.of<LoggingService>(context, listen: false);
                loggingService.logUserAction('Retry Dashboard Load', screen: 'DashboardScreen');
                _loadData();
              },
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
            const SizedBox(height: AppTheme.spacingM),
            OutlinedButton.icon(
              onPressed: _disconnect,
              icon: const Icon(Icons.logout),
              label: const Text('Change Server'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUpcomingEvents() {
    if (_upcomingEvents.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(AppTheme.spacingL),
          child: Column(
            children: [
              const Icon(
                Icons.event_available,
                size: 48,
                color: AppTheme.textTertiary,
              ),
              const SizedBox(height: AppTheme.spacingM),
              Text(
                'No upcoming events',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: AppTheme.textSecondary,
                ),
              ),
              const SizedBox(height: AppTheme.spacingS),
              Text(
                'Events scheduled for the next 7 days will appear here',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      children: _upcomingEvents.map((event) => Card(
        margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
        child: ListTile(
          leading: CircleAvatar(
            backgroundColor: _getEventColor(event.importance),
            child: Text(
              event.importance.toString(),
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          title: Text(event.title),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('👤 ${event.userName}'),
              Text('📅 ${event.formattedDate}${event.hasTime ? ' at ${event.formattedTime}' : ''}'),
              if (event.description != null && event.description!.isNotEmpty)
                Text('📝 ${event.description}'),
            ],
          ),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {
            // TODO: Navigate to event details
          },
        ),
      )).toList(),
    );
  }

  Widget _buildQuickActions() {
    final actions = [
      {
        'title': 'AI Chat',
        'subtitle': 'Chat with the AI',
        'icon': Icons.chat,
        'color': AppTheme.primaryColor,
        'onTap': () {
          Navigator.pushNamed(context, '/chat');
        },
      },
      {
        'title': 'Conversations',
        'subtitle': 'View chat history',
        'icon': Icons.history,
        'color': AppTheme.infoColor,
        'onTap': () {
          Navigator.pushNamed(context, '/conversations');
        },
      },
      {
        'title': 'Memories',
        'subtitle': 'Manage AI memories',
        'icon': Icons.psychology,
        'color': AppTheme.successColor,
        'onTap': () {
          Navigator.pushNamed(context, '/memories');
        },
      },
      {
        'title': 'Schedule',
        'subtitle': 'Manage events',
        'icon': Icons.calendar_today,
        'color': AppTheme.warningColor,
        'onTap': () {
          Navigator.pushNamed(context, '/schedule');
        },
      },
      {
        'title': 'Voice Config',
        'subtitle': 'Configure TTS voices',
        'icon': Icons.record_voice_over,
        'color': AppTheme.infoColor,
        'onTap': () {
          Navigator.pushNamed(context, '/voice-config');
        },
      },
      {
        'title': 'Ollama Config',
        'subtitle': 'Configure AI models',
        'icon': Icons.psychology,
        'color': AppTheme.primaryColor,
        'onTap': () {
          Navigator.pushNamed(context, '/ollama-config');
        },
      },
      {
        'title': 'Email Settings',
        'subtitle': 'Configure email settings',
        'icon': Icons.email,
        'color': AppTheme.infoColor,
        'onTap': () {
          Navigator.pushNamed(context, '/email-settings');
        },
      },
      {
        'title': 'Email Logs',
        'subtitle': 'View email history',
        'icon': Icons.history,
        'color': AppTheme.textSecondary,
        'onTap': () {
          Navigator.pushNamed(context, '/email-logs');
        },
      },
      {
        'title': 'Persona',
        'subtitle': 'Manage AI personality',
        'icon': Icons.person,
        'color': AppTheme.successColor,
        'onTap': () {
          Navigator.pushNamed(context, '/persona');
        },
      },
      {
        'title': 'Advanced Settings',
        'subtitle': 'Fine-tune AI behavior',
        'icon': Icons.settings,
        'color': AppTheme.warningColor,
        'onTap': () {
          Navigator.pushNamed(context, '/advanced-settings');
        },
      },
      {
        'title': 'Whisper Language',
        'subtitle': 'Set speech recognition language',
        'icon': Icons.language,
        'color': AppTheme.primaryColor,
        'onTap': () {
          Navigator.pushNamed(context, '/whisper-language');
        },
      },
    ];

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 1.2,
      crossAxisSpacing: AppTheme.spacingM,
      mainAxisSpacing: AppTheme.spacingM,
      children: actions.map((action) => Card(
        child: InkWell(
          onTap: action['onTap'] as VoidCallback,
          borderRadius: BorderRadius.circular(AppTheme.radiusL),
          child: Padding(
            padding: const EdgeInsets.all(AppTheme.spacingM),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  action['icon'] as IconData,
                  size: 32,
                  color: action['color'] as Color,
                ),
                const SizedBox(height: AppTheme.spacingS),
                Text(
                  action['title'] as String,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AppTheme.spacingXS),
                Text(
                  action['subtitle'] as String,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      )).toList(),
    );
  }

  Color _getEventColor(int importance) {
    if (importance >= 8) return AppTheme.errorColor;
    if (importance >= 5) return AppTheme.warningColor;
    return AppTheme.primaryColor;
  }

  Future<void> _sendLogsToServer() async {
    try {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      final apiService = Provider.of<ApiService>(context, listen: false);
      
      final success = await loggingService.sendLogsToServer(apiService);
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(success 
                ? 'Logs sent to server successfully' 
                : 'Failed to send logs to server'),
            backgroundColor: success ? AppTheme.successColor : AppTheme.errorColor,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error sending logs: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  Future<void> _disconnect() async {
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logUserAction('Disconnect from Server', screen: 'DashboardScreen');
    loggingService.logNavigation('DashboardScreen', 'ServerConnectScreen');
    
    final storageService = Provider.of<StorageService>(context, listen: false);
    await storageService.removeServerUrl();
    if (mounted) {
      Navigator.pushReplacementNamed(context, '/connect');
    }
  }
}
