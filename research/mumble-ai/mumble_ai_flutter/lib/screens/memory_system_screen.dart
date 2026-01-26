import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../services/logging_service.dart';
import '../models/entity.dart';
import '../models/memory_status.dart';
import '../models/memory_stats.dart';
import '../models/consolidation_log.dart';
import '../widgets/loading_indicator.dart';
import '../widgets/memory_search_bar.dart';
import '../widgets/search_result_card.dart';
import '../widgets/entity_card.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class MemorySystemScreen extends StatefulWidget {
  const MemorySystemScreen({Key? key}) : super(key: key);

  @override
  State<MemorySystemScreen> createState() => _MemorySystemScreenState();
}

class _MemorySystemScreenState extends State<MemorySystemScreen> with TickerProviderStateMixin {
  late TabController _tabController;
  
  // Data
  MemoryStatus? _memoryStatus;
  MemoryStats? _memoryStats;
  ConsolidationSummary? _consolidationSummary;
  List<Entity> _entities = [];
  List<String> _users = [];
  
  // Search
  String _searchQuery = '';
  String _searchType = 'all';
  bool _isSearching = false;
  List<Map<String, dynamic>> _searchResults = [];
  
  // State
  bool _isLoading = true;
  String? _errorMessage;
  
  // Filters
  String? _selectedEntityType;
  String? _selectedEntityUser;
  String? _selectedConsolidationUser;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 5, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      await Future.wait([
        _loadMemoryStatus(),
        _loadMemoryStats(),
        _loadConsolidationHistory(),
        _loadEntities(),
        _loadUsers(),
      ]);

      setState(() {
        _isLoading = false;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemorySystemScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load data: ${e.toString()}';
      });
    }
  }

  Future<void> _loadMemoryStatus() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final status = await apiService.getMemoryStatus();
      setState(() {
        _memoryStatus = status;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemorySystemScreen');
    }
  }

  Future<void> _loadMemoryStats() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final stats = await apiService.getMemoryStats();
      setState(() {
        _memoryStats = stats;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemorySystemScreen');
    }
  }

  Future<void> _loadConsolidationHistory() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final summary = await apiService.getConsolidationHistory();
      setState(() {
        _consolidationSummary = summary;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemorySystemScreen');
    }
  }

  Future<void> _loadEntities() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final storageService = Provider.of<StorageService>(context, listen: false);
      
      final currentUser = await storageService.getSelectedUser();
      
      final response = await apiService.getEntities(
        page: 1,
        perPage: 100,
        userName: currentUser,
        entityType: _selectedEntityType,
      );

      final entitiesList = response['data']['entities'] as List;
      final entities = entitiesList
          .map((json) => Entity.fromJson(json))
          .toList();

      setState(() {
        _entities = entities;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemorySystemScreen');
      setState(() {
        _entities = [];
      });
    }
  }

  Future<void> _loadUsers() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.usersEndpoint);
      
      List<dynamic> usersList;
      if (response.data is Map<String, dynamic>) {
        usersList = response.data['data'] as List;
      } else if (response.data is List) {
        usersList = response.data as List;
      } else {
        throw Exception('Unexpected response format');
      }
      
      setState(() {
        _users = usersList.map((item) => item.toString()).toList();
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemorySystemScreen');
      setState(() {
        _users = [];
      });
    }
  }

  Future<void> _performSearch(String query, String searchType) async {
    if (query.trim().isEmpty) {
      setState(() {
        _searchQuery = '';
        _searchType = searchType;
        _isSearching = false;
        _searchResults = [];
      });
      return;
    }

    setState(() {
      _searchQuery = query;
      _searchType = searchType;
      _isSearching = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final storageService = Provider.of<StorageService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final currentUser = await storageService.getSelectedUser();
      
      final response = await apiService.searchMemories(
        query: query,
        searchType: searchType,
        userName: currentUser,
        limit: 50,
      );

      final conversations = response['data']['conversations'] as List? ?? [];
      final entities = response['data']['entities'] as List? ?? [];
      
      final results = <Map<String, dynamic>>[];
      
      // Add conversations to results
      for (final conv in conversations) {
        results.add({
          'type': 'conversation',
          'content': conv['message'] ?? '',
          'userName': conv['user_name'],
          'timestamp': conv['created_at'],
          'relevanceScore': conv['relevance_score']?.toDouble(),
        });
      }
      
      // Add entities to results
      for (final entity in entities) {
        results.add({
          'type': 'entity',
          'content': entity['entity_text'] ?? '',
          'userName': entity['user_name'],
          'timestamp': entity['created_at'],
          'relevanceScore': entity['relevance_score']?.toDouble(),
          'entityType': entity['entity_type'],
          'contextInfo': entity['context_info'],
        });
      }
      
      // Sort by relevance score
      results.sort((a, b) {
        final scoreA = a['relevanceScore'] as double? ?? 0.0;
        final scoreB = b['relevanceScore'] as double? ?? 0.0;
        return scoreB.compareTo(scoreA);
      });

      setState(() {
        _searchResults = results;
        _isSearching = false;
      });
      
      loggingService.info('Search completed', screen: 'MemorySystemScreen', data: {
        'query': query,
        'searchType': searchType,
        'resultsCount': results.length,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemorySystemScreen');
      
      setState(() {
        _isSearching = false;
        _searchResults = [];
      });
    }
  }

  Future<void> _triggerConsolidation(String userName, int cutoffDays) async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Trigger Consolidation', screen: 'MemorySystemScreen', data: {
        'userName': userName,
        'cutoffDays': cutoffDays,
      });
      
      await apiService.triggerConsolidation(
        userName: userName,
        cutoffDays: cutoffDays,
      );

      // Reload consolidation history
      await _loadConsolidationHistory();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Consolidation triggered successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemorySystemScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to trigger consolidation: ${e.toString()}'),
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
        title: const Text('Memory System'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
            tooltip: 'Refresh',
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: const [
            Tab(icon: Icon(Icons.dashboard), text: 'Overview'),
            Tab(icon: Icon(Icons.label), text: 'Entities'),
            Tab(icon: Icon(Icons.merge), text: 'Consolidation'),
            Tab(icon: Icon(Icons.search), text: 'Search'),
            Tab(icon: Icon(Icons.analytics), text: 'Stats'),
          ],
        ),
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading memory system...')
          : _errorMessage != null
              ? _buildErrorState()
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildOverviewTab(),
                    _buildEntitiesTab(),
                    _buildConsolidationTab(),
                    _buildSearchTab(),
                    _buildStatsTab(),
                  ],
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
              'Error Loading Memory System',
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

  Widget _buildOverviewTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_memoryStatus != null) _buildSystemHealthCard(),
          const SizedBox(height: AppTheme.spacingM),
          if (_memoryStats != null) _buildKeyMetricsCard(),
          const SizedBox(height: AppTheme.spacingM),
          if (_consolidationSummary != null) _buildConsolidationSummaryCard(),
        ],
      ),
    );
  }

  Widget _buildSystemHealthCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  _memoryStatus!.isHealthy ? Icons.check_circle : Icons.error,
                  color: _memoryStatus!.isHealthy ? AppTheme.successColor : AppTheme.errorColor,
                ),
                const SizedBox(width: AppTheme.spacingS),
                Text(
                  'System Health',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                _buildHealthIndicator('Redis', _memoryStatus!.redis.status, _memoryStatus!.redis.info.memoryUsage),
                const SizedBox(width: AppTheme.spacingM),
                _buildHealthIndicator('ChromaDB', _memoryStatus!.chromadb.status, '${_memoryStatus!.chromadb.info.totalDocuments} docs'),
                const SizedBox(width: AppTheme.spacingM),
                _buildHealthIndicator('PostgreSQL', _memoryStatus!.postgresql.status, '${_memoryStatus!.postgresql.info.tablesCount} tables'),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'Entities: ${_memoryStatus!.entities.count} | '
              'Consolidated: ${_memoryStatus!.consolidation.stats.messagesConsolidated} messages',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHealthIndicator(String name, String status, String info) {
    final isHealthy = status == 'healthy';
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        decoration: BoxDecoration(
          color: isHealthy ? AppTheme.successColor.withOpacity(0.1) : AppTheme.errorColor.withOpacity(0.1),
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          border: Border.all(
            color: isHealthy ? AppTheme.successColor : AppTheme.errorColor,
          ),
        ),
        child: Column(
          children: [
            Icon(
              isHealthy ? Icons.check_circle : Icons.error,
              color: isHealthy ? AppTheme.successColor : AppTheme.errorColor,
              size: 24,
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              name,
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: isHealthy ? AppTheme.successColor : AppTheme.errorColor,
              ),
            ),
            const SizedBox(height: AppTheme.spacingXS),
            Text(
              info,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildKeyMetricsCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Key Metrics',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: _buildMetricItem(
                    'Conversations',
                    _memoryStats!.totalConversations.toString(),
                    Icons.chat,
                    AppTheme.infoColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Entities',
                    _memoryStats!.totalEntities.toString(),
                    Icons.label,
                    AppTheme.warningColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Users',
                    _memoryStats!.totalUsers.toString(),
                    Icons.people,
                    AppTheme.successColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: _buildMetricItem(
                    'Memory Usage',
                    _memoryStats!.memoryUsage.totalFormatted,
                    Icons.storage,
                    AppTheme.primaryColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Search Time',
                    '${_memoryStats!.searchPerformance.avgSearchTimeMs.toStringAsFixed(0)}ms',
                    Icons.search,
                    AppTheme.infoColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Cache Hit Rate',
                    _memoryStats!.searchPerformance.cacheHitRateFormatted,
                    Icons.speed,
                    AppTheme.successColor,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricItem(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: AppTheme.spacingS),
          Text(
            value,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.textSecondary,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildConsolidationSummaryCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Consolidation Summary',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: _buildMetricItem(
                    'Total Runs',
                    _consolidationSummary!.totalRuns.toString(),
                    Icons.play_arrow,
                    AppTheme.primaryColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Messages Consolidated',
                    _consolidationSummary!.totalMessagesConsolidated.toString(),
                    Icons.merge,
                    AppTheme.infoColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Tokens Saved',
                    _consolidationSummary!.totalTokensSavedFormatted,
                    Icons.savings,
                    AppTheme.successColor,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEntitiesTab() {
    return Column(
      children: [
        _buildEntityFilters(),
        Expanded(
          child: _entities.isEmpty
              ? _buildEmptyEntitiesState()
              : RefreshIndicator(
                  onRefresh: _loadEntities,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(AppTheme.spacingM),
                    itemCount: _entities.length,
                    itemBuilder: (context, index) {
                      final entity = _entities[index];
                      return EntityCard(
                        entity: entity,
                        onEdit: () => _showEditEntityDialog(entity),
                        onDelete: () => _deleteEntity(entity.id),
                      );
                    },
                  ),
                ),
        ),
      ],
    );
  }

  Widget _buildEntityFilters() {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: const Border(
          bottom: BorderSide(color: AppTheme.borderColor),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: DropdownButtonFormField<String>(
              value: _selectedEntityUser,
              decoration: const InputDecoration(
                labelText: 'User',
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.symmetric(
                  horizontal: AppTheme.spacingM,
                  vertical: AppTheme.spacingS,
                ),
              ),
              items: [
                const DropdownMenuItem<String>(
                  value: null,
                  child: Text('All Users'),
                ),
                ..._users.map((user) => DropdownMenuItem<String>(
                  value: user,
                  child: Text(user),
                )),
              ],
              onChanged: (value) {
                setState(() {
                  _selectedEntityUser = value;
                });
                _loadEntities();
              },
            ),
          ),
          const SizedBox(width: AppTheme.spacingM),
          Expanded(
            child: DropdownButtonFormField<String>(
              value: _selectedEntityType,
              decoration: const InputDecoration(
                labelText: 'Entity Type',
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.symmetric(
                  horizontal: AppTheme.spacingM,
                  vertical: AppTheme.spacingS,
                ),
              ),
              items: [
                const DropdownMenuItem<String>(
                  value: null,
                  child: Text('All Types'),
                ),
                ...AppConstants.entityTypes.map((type) => DropdownMenuItem<String>(
                  value: type,
                  child: Text(AppConstants.entityTypeDisplayNames[type] ?? type),
                )),
              ],
              onChanged: (value) {
                setState(() {
                  _selectedEntityType = value;
                });
                _loadEntities();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyEntitiesState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.label_outline,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'No Entities',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Entities will appear here as the AI extracts them from conversations',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConsolidationTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_consolidationSummary != null) ...[
            _buildConsolidationSummaryCard(),
            const SizedBox(height: AppTheme.spacingM),
            _buildConsolidationTriggerCard(),
            const SizedBox(height: AppTheme.spacingM),
            _buildConsolidationHistoryCard(),
          ],
        ],
      ),
    );
  }

  Widget _buildConsolidationTriggerCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Manual Consolidation',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    value: _selectedConsolidationUser,
                    decoration: const InputDecoration(
                      labelText: 'User',
                      border: OutlineInputBorder(),
                    ),
                    items: [
                      const DropdownMenuItem<String>(
                        value: null,
                        child: Text('Select User'),
                      ),
                      ..._users.map((user) => DropdownMenuItem<String>(
                        value: user,
                        child: Text(user),
                      )),
                    ],
                    onChanged: (value) {
                      setState(() {
                        _selectedConsolidationUser = value;
                      });
                    },
                  ),
                ),
                const SizedBox(width: AppTheme.spacingM),
                ElevatedButton.icon(
                  onPressed: _selectedConsolidationUser != null
                      ? () => _showConsolidationDialog()
                      : null,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Trigger'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConsolidationHistoryCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Consolidation History',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            if (_consolidationSummary!.history.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(AppTheme.spacingL),
                  child: Text('No consolidation history available'),
                ),
              )
            else
              ListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _consolidationSummary!.history.length,
                itemBuilder: (context, index) {
                  final log = _consolidationSummary!.history[index];
                  return ListTile(
                    leading: const Icon(Icons.merge),
                    title: Text(log.userName),
                    subtitle: Text('${log.messagesConsolidated} messages → ${log.summariesCreated} summaries'),
                    trailing: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(log.runAtFormatted),
                        Text(
                          '${log.tokensSavedFormatted} tokens saved',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppTheme.successColor,
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildSearchTab() {
    return Column(
      children: [
        MemorySearchBar(
          initialQuery: _searchQuery,
          initialSearchType: _searchType,
          onSearch: _performSearch,
          onClear: () {
            setState(() {
              _searchQuery = '';
              _searchResults = [];
            });
          },
          isLoading: _isSearching,
        ),
        Expanded(
          child: _searchQuery.isEmpty
              ? _buildEmptySearchState()
              : _isSearching
                  ? const Center(child: LoadingIndicator(message: 'Searching...'))
                  : _searchResults.isEmpty
                      ? _buildNoSearchResultsState()
                      : RefreshIndicator(
                          onRefresh: () => _performSearch(_searchQuery, _searchType),
                          child: ListView.builder(
                            padding: const EdgeInsets.all(AppTheme.spacingM),
                            itemCount: _searchResults.length,
                            itemBuilder: (context, index) {
                              final result = _searchResults[index];
                              return SearchResultCard(
                                type: result['type'],
                                content: result['content'],
                                userName: result['userName'],
                                timestamp: result['timestamp'],
                                relevanceScore: result['relevanceScore'],
                                entityType: result['entityType'],
                                contextInfo: result['contextInfo'],
                                onTap: () {
                                  // Handle tap on search result
                                },
                              );
                            },
                          ),
                        ),
        ),
      ],
    );
  }

  Widget _buildEmptySearchState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.search,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'Search Memories & Entities',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Use the search bar above to find specific memories or entities',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNoSearchResultsState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.search_off,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'No Results Found',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Try a different search term or search type',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatsTab() {
    if (_memoryStats == null) {
      return const Center(child: LoadingIndicator(message: 'Loading stats...'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildKeyMetricsCard(),
          const SizedBox(height: AppTheme.spacingM),
          _buildMemoryUsageCard(),
          const SizedBox(height: AppTheme.spacingM),
          _buildSearchPerformanceCard(),
          const SizedBox(height: AppTheme.spacingM),
          _buildConsolidationEfficiencyCard(),
        ],
      ),
    );
  }

  Widget _buildMemoryUsageCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Memory Usage',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: _buildMetricItem(
                    'Redis',
                    '${_memoryStats!.memoryUsage.redisMb.toStringAsFixed(1)} MB',
                    Icons.memory,
                    AppTheme.errorColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'PostgreSQL',
                    '${_memoryStats!.memoryUsage.postgresqlMb.toStringAsFixed(1)} MB',
                    Icons.storage,
                    AppTheme.infoColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'ChromaDB',
                    '${_memoryStats!.memoryUsage.chromadbMb.toStringAsFixed(1)} MB',
                    Icons.analytics,
                    AppTheme.warningColor,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSearchPerformanceCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Search Performance',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: _buildMetricItem(
                    'Avg Search Time',
                    '${_memoryStats!.searchPerformance.avgSearchTimeMs.toStringAsFixed(0)}ms',
                    Icons.speed,
                    AppTheme.primaryColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Total Searches',
                    _memoryStats!.searchPerformance.totalSearches.toString(),
                    Icons.search,
                    AppTheme.infoColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Cache Hit Rate',
                    _memoryStats!.searchPerformance.cacheHitRateFormatted,
                    Icons.cached,
                    AppTheme.successColor,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConsolidationEfficiencyCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Consolidation Efficiency',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: _buildMetricItem(
                    'Efficiency Ratio',
                    _memoryStats!.consolidationStats.efficiencyRatioFormatted,
                    Icons.trending_up,
                    AppTheme.successColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Tokens Saved',
                    _memoryStats!.consolidationStats.totalTokensSavedFormatted,
                    Icons.savings,
                    AppTheme.warningColor,
                  ),
                ),
                Expanded(
                  child: _buildMetricItem(
                    'Last Run',
                    _memoryStats!.consolidationStats.lastRun != null
                        ? 'Recent'
                        : 'Never',
                    Icons.schedule,
                    AppTheme.infoColor,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _showConsolidationDialog() {
    int cutoffDays = 7;
    
    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('Trigger Consolidation'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('User: $_selectedConsolidationUser'),
              const SizedBox(height: AppTheme.spacingM),
              Text('Cutoff Days: $cutoffDays'),
              Slider(
                value: cutoffDays.toDouble(),
                min: 1,
                max: 30,
                divisions: 29,
                label: '$cutoffDays days',
                onChanged: (value) {
                  setState(() {
                    cutoffDays = value.round();
                  });
                },
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(context);
                _triggerConsolidation(_selectedConsolidationUser!, cutoffDays);
              },
              child: const Text('Trigger'),
            ),
          ],
        ),
      ),
    );
  }

  void _showEditEntityDialog(Entity entity) {
    // Implementation would be similar to the one in memories_screen.dart
    // For brevity, I'm not duplicating it here
  }

  Future<void> _deleteEntity(int entityId) async {
    // Implementation would be similar to the one in memories_screen.dart
    // For brevity, I'm not duplicating it here
  }
}
