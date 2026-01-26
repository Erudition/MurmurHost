import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../services/logging_service.dart';
import '../models/memory.dart';
import '../models/entity.dart';
import '../models/memory_status.dart';
import '../widgets/loading_indicator.dart';
import '../widgets/memory_search_bar.dart';
import '../widgets/search_result_card.dart';
import '../widgets/entity_card.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class MemoriesScreen extends StatefulWidget {
  const MemoriesScreen({Key? key}) : super(key: key);

  @override
  State<MemoriesScreen> createState() => _MemoriesScreenState();
}

class _MemoriesScreenState extends State<MemoriesScreen> with TickerProviderStateMixin {
  List<Memory> _memories = [];
  List<Entity> _entities = [];
  List<String> _users = [];
  bool _isLoading = true;
  String? _errorMessage;
  String? _selectedUser;
  String? _selectedCategory;
  
  // Search functionality
  String _searchQuery = '';
  String _searchType = 'all';
  bool _isSearching = false;
  List<Map<String, dynamic>> _searchResults = [];
  
  // Tab management
  late TabController _tabController;
  int _currentTabIndex = 0;
  
  // Entity management
  String? _selectedEntityType;
  String? _selectedEntityUser;
  
  // System status
  MemoryStatus? _memoryStatus;
  bool _showSystemStatus = false;

  @override
  void initState() {
    super.initState();
    
    // Initialize tab controller
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(() {
      setState(() {
        _currentTabIndex = _tabController.index;
      });
    });
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('MemoriesScreen', 'initState');
    
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
      // Load memories, entities, users, and system status in parallel
      await Future.wait([
        _loadMemories(),
        _loadEntities(),
        _loadUsers(),
        _loadMemoryStatus(),
      ]);

      setState(() {
        _isLoading = false;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load data: ${e.toString()}';
      });
    }
  }

  Future<void> _loadMemories() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final storageService = Provider.of<StorageService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final queryParams = <String, dynamic>{};
      
      // Always include the selected user from storage
      final currentUser = await storageService.getSelectedUser();
      if (currentUser != null) {
        queryParams['user_name'] = currentUser;
      }
      
      if (_selectedCategory != null) {
        queryParams['category'] = _selectedCategory;
      }

      final response = await apiService.get(
        AppConstants.memoriesEndpoint,
        queryParameters: queryParams,
      );

      // Handle both new wrapped format and legacy array format
      List<dynamic> memoriesList;
      if (response.data is Map<String, dynamic>) {
        // New wrapped format: {"success": true, "data": {"memories": [...], "pagination": {...}}}
        final data = response.data['data'];
        memoriesList = data['memories'] as List;
      } else if (response.data is List) {
        // Legacy format: [...]
        memoriesList = response.data as List;
      } else {
        throw Exception('Unexpected response format: expected Map or List, got ${response.data.runtimeType}');
      }

      final memories = memoriesList
          .map((json) => Memory.fromJson(json))
          .toList();

      setState(() {
        _memories = memories;
      });
      
      loggingService.info('Memories loaded successfully', screen: 'MemoriesScreen', data: {
        'count': memories.length,
        'user': currentUser,
        'category': _selectedCategory,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      throw Exception('Failed to load memories: $e');
    }
  }

  Future<void> _loadUsers() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.usersEndpoint);
      
      // Handle both new wrapped format and legacy array format
      List<dynamic> usersList;
      if (response.data is Map<String, dynamic>) {
        // New wrapped format (if backend is updated)
        usersList = response.data['data'] as List;
      } else if (response.data is List) {
        // Legacy format (current)
        usersList = response.data as List;
      } else {
        throw Exception('Unexpected response format: expected Map or List, got ${response.data.runtimeType}');
      }
      
      setState(() {
        _users = usersList.map((item) => item.toString()).toList();
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      // Don't throw error for users, just log it
      setState(() {
        _users = [];
      });
    }
  }

  Future<void> _loadEntities() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final storageService = Provider.of<StorageService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final queryParams = <String, dynamic>{};
      
      // Always include the selected user from storage
      final currentUser = await storageService.getSelectedUser();
      if (currentUser != null) {
        queryParams['user_name'] = currentUser;
      }
      
      if (_selectedEntityType != null) {
        queryParams['entity_type'] = _selectedEntityType;
      }

      final response = await apiService.getEntities(
        page: 1,
        perPage: 100,
        userName: queryParams['user_name'],
        entityType: queryParams['entity_type'],
      );

      final entitiesList = response['data']['entities'] as List;
      final entities = entitiesList
          .map((json) => Entity.fromJson(json))
          .toList();

      setState(() {
        _entities = entities;
      });
      
      loggingService.info('Entities loaded successfully', screen: 'MemoriesScreen', data: {
        'count': entities.length,
        'user': currentUser,
        'entityType': _selectedEntityType,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      // Don't throw error for entities, just log it
      setState(() {
        _entities = [];
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
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      // Don't throw error for status, just log it
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
      
      loggingService.info('Search completed', screen: 'MemoriesScreen', data: {
        'query': query,
        'searchType': searchType,
        'resultsCount': results.length,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      setState(() {
        _isSearching = false;
        _searchResults = [];
      });
    }
  }

  Future<void> _deleteMemory(int memoryId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Memory'),
        content: const Text('Are you sure you want to delete this memory?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(primary: AppTheme.errorColor),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final apiService = Provider.of<ApiService>(context, listen: false);
        final loggingService = Provider.of<LoggingService>(context, listen: false);
        
        loggingService.logUserAction('Delete Memory', screen: 'MemoriesScreen', data: {
          'memoryId': memoryId,
        });
        
        await apiService.delete('${AppConstants.memoriesEndpoint}/$memoryId');
        
        setState(() {
          _memories.removeWhere((memory) => memory.id == memoryId);
        });

        loggingService.info('Memory deleted successfully', screen: 'MemoriesScreen', data: {
          'memoryId': memoryId,
        });

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Memory deleted successfully'),
              backgroundColor: AppTheme.successColor,
            ),
          );
        }
      } catch (e, stackTrace) {
        final loggingService = Provider.of<LoggingService>(context, listen: false);
        loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to delete memory: ${e.toString()}'),
              backgroundColor: AppTheme.errorColor,
            ),
          );
        }
      }
    }
  }

  void _showAddMemoryDialog() {
    showDialog(
      context: context,
      builder: (context) => _AddMemoryDialog(
        users: _users,
        onMemoryAdded: () {
          _loadMemories();
        },
      ),
    );
  }

  void _showEditMemoryDialog(Memory memory) {
    showDialog(
      context: context,
      builder: (context) => _EditMemoryDialog(
        memory: memory,
        users: _users,
        onMemoryUpdated: () {
          _loadMemories();
        },
      ),
    );
  }

  Color _getImportanceColor(int importance) {
    if (importance >= 8) return AppTheme.errorColor;
    if (importance >= 5) return AppTheme.warningColor;
    return AppTheme.primaryColor;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Memories & Entities'),
        actions: [
          IconButton(
            icon: const Icon(Icons.chat),
            onPressed: () {
              Navigator.pushNamed(context, '/chat');
            },
            tooltip: 'Ask AI about your memories',
          ),
          IconButton(
            icon: Icon(_showSystemStatus ? Icons.visibility_off : Icons.visibility),
            onPressed: () {
              setState(() {
                _showSystemStatus = !_showSystemStatus;
              });
            },
            tooltip: _showSystemStatus ? 'Hide system status' : 'Show system status',
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
            tooltip: 'Refresh',
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.psychology), text: 'Memories'),
            Tab(icon: Icon(Icons.label), text: 'Entities'),
            Tab(icon: Icon(Icons.search), text: 'Search'),
          ],
        ),
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading memories...')
          : _errorMessage != null
              ? _buildErrorState()
              : Column(
                  children: [
                    if (_showSystemStatus && _memoryStatus != null)
                      _buildSystemStatusCard(),
                    if (_currentTabIndex == 2) // Search tab
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
                      child: TabBarView(
                        controller: _tabController,
                        children: [
                          _buildMemoriesTab(),
                          _buildEntitiesTab(),
                          _buildSearchTab(),
                        ],
                      ),
                    ),
                  ],
                ),
      floatingActionButton: _currentTabIndex == 0 // Only show for memories tab
          ? FloatingActionButton(
              onPressed: _showAddMemoryDialog,
              child: const Icon(Icons.add),
            )
          : _currentTabIndex == 1 // Show add entity for entities tab
              ? FloatingActionButton(
                  onPressed: _showAddEntityDialog,
                  child: const Icon(Icons.add),
                )
              : null,
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
              'Error Loading Memories',
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

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.psychology_outlined,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'No Memories',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Memories will appear here as the AI learns about users',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppTheme.spacingL),
            ElevatedButton.icon(
              onPressed: _showAddMemoryDialog,
              icon: const Icon(Icons.add),
              label: const Text('Add Memory'),
            ),
            const SizedBox(height: AppTheme.spacingM),
            TextButton.icon(
              onPressed: () {
                Navigator.pushNamed(context, '/chat');
              },
              icon: const Icon(Icons.chat),
              label: const Text('Ask AI about memories'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilters() {
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
              value: _selectedUser,
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
                  _selectedUser = value;
                });
                _loadMemories();
              },
            ),
          ),
          const SizedBox(width: AppTheme.spacingM),
          Expanded(
            child: DropdownButtonFormField<String>(
              value: _selectedCategory,
              decoration: const InputDecoration(
                labelText: 'Category',
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.symmetric(
                  horizontal: AppTheme.spacingM,
                  vertical: AppTheme.spacingS,
                ),
              ),
              items: [
                const DropdownMenuItem<String>(
                  value: null,
                  child: Text('All Categories'),
                ),
                ...AppConstants.memoryCategories.map((category) => DropdownMenuItem<String>(
                  value: category,
                  child: Text(AppConstants.memoryCategoryDisplayNames[category] ?? category),
                )),
              ],
              onChanged: (value) {
                setState(() {
                  _selectedCategory = value;
                });
                _loadMemories();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMemoryCard(Memory memory) {
    return Card(
      margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
      child: InkWell(
        onTap: () => _showEditMemoryDialog(memory),
        borderRadius: BorderRadius.circular(AppTheme.radiusL),
        child: Padding(
          padding: const EdgeInsets.all(AppTheme.spacingM),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppTheme.spacingS,
                      vertical: AppTheme.spacingXS,
                    ),
                    decoration: BoxDecoration(
                      color: _getImportanceColor(memory.importance).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(AppTheme.radiusS),
                      border: Border.all(
                        color: _getImportanceColor(memory.importance).withOpacity(0.3),
                      ),
                    ),
                    child: Text(
                      memory.importanceLevel,
                      style: TextStyle(
                        color: _getImportanceColor(memory.importance),
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingS),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppTheme.spacingS,
                      vertical: AppTheme.spacingXS,
                    ),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(AppTheme.radiusS),
                      border: Border.all(
                        color: AppTheme.primaryColor.withOpacity(0.3),
                      ),
                    ),
                    child: Text(
                      memory.categoryDisplay,
                      style: const TextStyle(
                        color: AppTheme.primaryColor,
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const Spacer(),
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      if (value == 'edit') {
                        _showEditMemoryDialog(memory);
                      } else if (value == 'delete') {
                        _deleteMemory(memory.id);
                      }
                    },
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                        value: 'edit',
                        child: ListTile(
                          leading: Icon(Icons.edit),
                          title: Text('Edit'),
                          contentPadding: EdgeInsets.zero,
                        ),
                      ),
                      const PopupMenuItem(
                        value: 'delete',
                        child: ListTile(
                          leading: Icon(Icons.delete, color: AppTheme.errorColor),
                          title: Text('Delete', style: TextStyle(color: AppTheme.errorColor)),
                          contentPadding: EdgeInsets.zero,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: AppTheme.spacingS),
              Text(
                memory.userName,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textSecondary,
                ),
              ),
              const SizedBox(height: AppTheme.spacingS),
              Text(
                memory.content,
                style: AppTheme.messageBubbleStyle,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
              if (memory.tags.isNotEmpty) ...[
                const SizedBox(height: AppTheme.spacingS),
                Wrap(
                  spacing: AppTheme.spacingXS,
                  runSpacing: AppTheme.spacingXS,
                  children: memory.tags.map((tag) => Chip(
                    label: Text(tag),
                    backgroundColor: AppTheme.backgroundColor,
                    labelStyle: const TextStyle(fontSize: 12),
                  )).toList(),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSystemStatusCard() {
    if (_memoryStatus == null) return const SizedBox.shrink();
    
    return Container(
      margin: const EdgeInsets.all(AppTheme.spacingM),
      child: Card(
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
                    'Memory System Status',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () {
                      setState(() {
                        _showSystemStatus = false;
                      });
                    },
                  ),
                ],
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  _buildStatusIndicator('Redis', _memoryStatus!.redis.status),
                  const SizedBox(width: AppTheme.spacingM),
                  _buildStatusIndicator('ChromaDB', _memoryStatus!.chromadb.status),
                  const SizedBox(width: AppTheme.spacingM),
                  _buildStatusIndicator('PostgreSQL', _memoryStatus!.postgresql.status),
                ],
              ),
              const SizedBox(height: AppTheme.spacingM),
              Text(
                'Entities: ${_memoryStatus!.entities.count} | '
                'Consolidated: ${_memoryStatus!.consolidation.stats.messagesConsolidated} messages',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusIndicator(String name, String status) {
    final isHealthy = status == 'healthy';
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          isHealthy ? Icons.check_circle : Icons.error,
          size: 16,
          color: isHealthy ? AppTheme.successColor : AppTheme.errorColor,
        ),
        const SizedBox(width: AppTheme.spacingXS),
        Text(
          name,
          style: TextStyle(
            fontSize: 12,
            color: isHealthy ? AppTheme.successColor : AppTheme.errorColor,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildMemoriesTab() {
    if (_memories.isEmpty) {
      return _buildEmptyMemoriesState();
    }
    
    return Column(
      children: [
        _buildMemoryFilters(),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _loadMemories,
            child: ListView.builder(
              padding: const EdgeInsets.all(AppTheme.spacingM),
              itemCount: _memories.length,
              itemBuilder: (context, index) {
                final memory = _memories[index];
                return _buildMemoryCard(memory);
              },
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildEntitiesTab() {
    if (_entities.isEmpty) {
      return _buildEmptyEntitiesState();
    }
    
    return Column(
      children: [
        _buildEntityFilters(),
        Expanded(
          child: RefreshIndicator(
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

  Widget _buildSearchTab() {
    if (_searchQuery.isEmpty) {
      return _buildEmptySearchState();
    }
    
    if (_isSearching) {
      return const Center(
        child: LoadingIndicator(message: 'Searching...'),
      );
    }
    
    if (_searchResults.isEmpty) {
      return _buildNoSearchResultsState();
    }
    
    return RefreshIndicator(
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
    );
  }

  Widget _buildEmptyMemoriesState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.psychology_outlined,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'No Memories',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Memories will appear here as the AI learns about users',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppTheme.spacingL),
            ElevatedButton.icon(
              onPressed: _showAddMemoryDialog,
              icon: const Icon(Icons.add),
              label: const Text('Add Memory'),
            ),
          ],
        ),
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
            const SizedBox(height: AppTheme.spacingL),
            ElevatedButton.icon(
              onPressed: _showAddEntityDialog,
              icon: const Icon(Icons.add),
              label: const Text('Add Entity'),
            ),
          ],
        ),
      ),
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

  Widget _buildMemoryFilters() {
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
              value: _selectedUser,
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
                  _selectedUser = value;
                });
                _loadMemories();
              },
            ),
          ),
          const SizedBox(width: AppTheme.spacingM),
          Expanded(
            child: DropdownButtonFormField<String>(
              value: _selectedCategory,
              decoration: const InputDecoration(
                labelText: 'Category',
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.symmetric(
                  horizontal: AppTheme.spacingM,
                  vertical: AppTheme.spacingS,
                ),
              ),
              items: [
                const DropdownMenuItem<String>(
                  value: null,
                  child: Text('All Categories'),
                ),
                ...AppConstants.memoryCategories.map((category) => DropdownMenuItem<String>(
                  value: category,
                  child: Text(AppConstants.memoryCategoryDisplayNames[category] ?? category),
                )),
              ],
              onChanged: (value) {
                setState(() {
                  _selectedCategory = value;
                });
                _loadMemories();
              },
            ),
          ),
        ],
      ),
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

  void _showAddEntityDialog() {
    showDialog(
      context: context,
      builder: (context) => _AddEntityDialog(
        users: _users,
        onEntityAdded: () {
          _loadEntities();
        },
      ),
    );
  }

  void _showEditEntityDialog(Entity entity) {
    showDialog(
      context: context,
      builder: (context) => _EditEntityDialog(
        entity: entity,
        users: _users,
        onEntityUpdated: () {
          _loadEntities();
        },
      ),
    );
  }

  Future<void> _deleteEntity(int entityId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Entity'),
        content: const Text('Are you sure you want to delete this entity?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(primary: AppTheme.errorColor),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final apiService = Provider.of<ApiService>(context, listen: false);
        final loggingService = Provider.of<LoggingService>(context, listen: false);
        
        loggingService.logUserAction('Delete Entity', screen: 'MemoriesScreen', data: {
          'entityId': entityId,
        });
        
        await apiService.deleteEntity(entityId);
        
        setState(() {
          _entities.removeWhere((entity) => entity.id == entityId);
        });

        loggingService.info('Entity deleted successfully', screen: 'MemoriesScreen', data: {
          'entityId': entityId,
        });

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Entity deleted successfully'),
              backgroundColor: AppTheme.successColor,
            ),
          );
        }
      } catch (e, stackTrace) {
        final loggingService = Provider.of<LoggingService>(context, listen: false);
        loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to delete entity: ${e.toString()}'),
              backgroundColor: AppTheme.errorColor,
            ),
          );
        }
      }
    }
  }
}

class _AddMemoryDialog extends StatefulWidget {
  final List<String> users;
  final VoidCallback onMemoryAdded;

  const _AddMemoryDialog({
    Key? key,
    required this.users,
    required this.onMemoryAdded,
  }) : super(key: key);

  @override
  State<_AddMemoryDialog> createState() => _AddMemoryDialogState();
}

class _AddMemoryDialogState extends State<_AddMemoryDialog> {
  final _formKey = GlobalKey<FormState>();
  final _userController = TextEditingController();
  final _contentController = TextEditingController();
  String _selectedCategory = 'other';
  int _importance = 5;

  @override
  void dispose() {
    _userController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  Future<void> _saveMemory() async {
    if (!_formKey.currentState!.validate()) return;

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Add Memory', screen: 'MemoriesScreen', data: {
        'user': _userController.text.trim(),
        'category': _selectedCategory,
        'importance': _importance,
      });
      
      await apiService.post(AppConstants.memoriesEndpoint, data: {
        'user_name': _userController.text.trim(),
        'category': _selectedCategory,
        'content': _contentController.text.trim(),
        'importance': _importance,
        'tags': [],
      });

      loggingService.info('Memory added successfully', screen: 'MemoriesScreen');

      widget.onMemoryAdded();
      Navigator.pop(context);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Memory added successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to add memory: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Memory'),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _userController,
                decoration: const InputDecoration(
                  labelText: 'User Name',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a user name';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              DropdownButtonFormField<String>(
                value: _selectedCategory,
                decoration: const InputDecoration(
                  labelText: 'Category',
                  border: OutlineInputBorder(),
                ),
                items: AppConstants.memoryCategories.map((category) => DropdownMenuItem<String>(
                  value: category,
                  child: Text(AppConstants.memoryCategoryDisplayNames[category] ?? category),
                )).toList(),
                onChanged: (value) {
                  setState(() {
                    _selectedCategory = value!;
                  });
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _contentController,
                decoration: const InputDecoration(
                  labelText: 'Content',
                  border: OutlineInputBorder(),
                ),
                maxLines: 3,
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter memory content';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  const Text('Importance: '),
                  Expanded(
                    child: Slider(
                      value: _importance.toDouble(),
                      min: 1,
                      max: 10,
                      divisions: 9,
                      label: _importance.toString(),
                      onChanged: (value) {
                        setState(() {
                          _importance = value.round();
                        });
                      },
                    ),
                  ),
                  Text(_importance.toString()),
                ],
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _saveMemory,
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class _EditMemoryDialog extends StatefulWidget {
  final Memory memory;
  final List<String> users;
  final VoidCallback onMemoryUpdated;

  const _EditMemoryDialog({
    Key? key,
    required this.memory,
    required this.users,
    required this.onMemoryUpdated,
  }) : super(key: key);

  @override
  State<_EditMemoryDialog> createState() => _EditMemoryDialogState();
}

class _EditMemoryDialogState extends State<_EditMemoryDialog> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _userController;
  late TextEditingController _contentController;
  late String _selectedCategory;
  late int _importance;

  @override
  void initState() {
    super.initState();
    _userController = TextEditingController(text: widget.memory.userName);
    _contentController = TextEditingController(text: widget.memory.content);
    _selectedCategory = widget.memory.category;
    _importance = widget.memory.importance;
  }

  @override
  void dispose() {
    _userController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  Future<void> _updateMemory() async {
    if (!_formKey.currentState!.validate()) return;

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Update Memory', screen: 'MemoriesScreen', data: {
        'memoryId': widget.memory.id,
        'user': _userController.text.trim(),
        'category': _selectedCategory,
        'importance': _importance,
      });
      
      await apiService.put('${AppConstants.memoriesEndpoint}/${widget.memory.id}', data: {
        'user_name': _userController.text.trim(),
        'category': _selectedCategory,
        'content': _contentController.text.trim(),
        'importance': _importance,
        'tags': widget.memory.tags,
      });

      loggingService.info('Memory updated successfully', screen: 'MemoriesScreen', data: {
        'memoryId': widget.memory.id,
      });

      widget.onMemoryUpdated();
      Navigator.pop(context);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Memory updated successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to update memory: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit Memory'),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _userController,
                decoration: const InputDecoration(
                  labelText: 'User Name',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a user name';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              DropdownButtonFormField<String>(
                value: _selectedCategory,
                decoration: const InputDecoration(
                  labelText: 'Category',
                  border: OutlineInputBorder(),
                ),
                items: AppConstants.memoryCategories.map((category) => DropdownMenuItem<String>(
                  value: category,
                  child: Text(AppConstants.memoryCategoryDisplayNames[category] ?? category),
                )).toList(),
                onChanged: (value) {
                  setState(() {
                    _selectedCategory = value!;
                  });
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _contentController,
                decoration: const InputDecoration(
                  labelText: 'Content',
                  border: OutlineInputBorder(),
                ),
                maxLines: 3,
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter memory content';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  const Text('Importance: '),
                  Expanded(
                    child: Slider(
                      value: _importance.toDouble(),
                      min: 1,
                      max: 10,
                      divisions: 9,
                      label: _importance.toString(),
                      onChanged: (value) {
                        setState(() {
                          _importance = value.round();
                        });
                      },
                    ),
                  ),
                  Text(_importance.toString()),
                ],
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _updateMemory,
          child: const Text('Update'),
        ),
      ],
    );
  }
}

class _AddEntityDialog extends StatefulWidget {
  final List<String> users;
  final VoidCallback onEntityAdded;

  const _AddEntityDialog({
    Key? key,
    required this.users,
    required this.onEntityAdded,
  }) : super(key: key);

  @override
  State<_AddEntityDialog> createState() => _AddEntityDialogState();
}

class _AddEntityDialogState extends State<_AddEntityDialog> {
  final _formKey = GlobalKey<FormState>();
  final _userController = TextEditingController();
  final _entityTextController = TextEditingController();
  final _contextInfoController = TextEditingController();
  String _selectedEntityType = 'OTHER';
  double _confidence = 1.0;

  @override
  void dispose() {
    _userController.dispose();
    _entityTextController.dispose();
    _contextInfoController.dispose();
    super.dispose();
  }

  Future<void> _saveEntity() async {
    if (!_formKey.currentState!.validate()) return;

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Add Entity', screen: 'MemoriesScreen', data: {
        'user': _userController.text.trim(),
        'entityType': _selectedEntityType,
        'confidence': _confidence,
      });
      
      await apiService.createEntity(
        entityText: _entityTextController.text.trim(),
        entityType: _selectedEntityType,
        userName: _userController.text.trim(),
        contextInfo: _contextInfoController.text.trim().isNotEmpty 
            ? _contextInfoController.text.trim() 
            : null,
        confidence: _confidence,
      );

      loggingService.info('Entity added successfully', screen: 'MemoriesScreen');

      widget.onEntityAdded();
      Navigator.pop(context);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Entity added successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to add entity: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Entity'),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _userController,
                decoration: const InputDecoration(
                  labelText: 'User Name',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a user name';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              DropdownButtonFormField<String>(
                value: _selectedEntityType,
                decoration: const InputDecoration(
                  labelText: 'Entity Type',
                  border: OutlineInputBorder(),
                ),
                items: AppConstants.entityTypes.map((type) => DropdownMenuItem<String>(
                  value: type,
                  child: Text(AppConstants.entityTypeDisplayNames[type] ?? type),
                )).toList(),
                onChanged: (value) {
                  setState(() {
                    _selectedEntityType = value!;
                  });
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _entityTextController,
                decoration: const InputDecoration(
                  labelText: 'Entity Text',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter entity text';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _contextInfoController,
                decoration: const InputDecoration(
                  labelText: 'Context Info (Optional)',
                  border: OutlineInputBorder(),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  const Text('Confidence: '),
                  Expanded(
                    child: Slider(
                      value: _confidence,
                      min: 0.0,
                      max: 1.0,
                      divisions: 10,
                      label: '${(_confidence * 100).toStringAsFixed(0)}%',
                      onChanged: (value) {
                        setState(() {
                          _confidence = value;
                        });
                      },
                    ),
                  ),
                  Text('${(_confidence * 100).toStringAsFixed(0)}%'),
                ],
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _saveEntity,
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class _EditEntityDialog extends StatefulWidget {
  final Entity entity;
  final List<String> users;
  final VoidCallback onEntityUpdated;

  const _EditEntityDialog({
    Key? key,
    required this.entity,
    required this.users,
    required this.onEntityUpdated,
  }) : super(key: key);

  @override
  State<_EditEntityDialog> createState() => _EditEntityDialogState();
}

class _EditEntityDialogState extends State<_EditEntityDialog> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _userController;
  late TextEditingController _entityTextController;
  late TextEditingController _contextInfoController;
  late String _selectedEntityType;
  late double _confidence;

  @override
  void initState() {
    super.initState();
    _userController = TextEditingController(text: widget.entity.userName);
    _entityTextController = TextEditingController(text: widget.entity.entityText);
    _contextInfoController = TextEditingController(text: widget.entity.contextInfo ?? '');
    _selectedEntityType = widget.entity.entityType;
    _confidence = widget.entity.confidence;
  }

  @override
  void dispose() {
    _userController.dispose();
    _entityTextController.dispose();
    _contextInfoController.dispose();
    super.dispose();
  }

  Future<void> _updateEntity() async {
    if (!_formKey.currentState!.validate()) return;

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Update Entity', screen: 'MemoriesScreen', data: {
        'entityId': widget.entity.id,
        'user': _userController.text.trim(),
        'entityType': _selectedEntityType,
        'confidence': _confidence,
      });
      
      await apiService.updateEntity(
        widget.entity.id,
        entityText: _entityTextController.text.trim(),
        contextInfo: _contextInfoController.text.trim().isNotEmpty 
            ? _contextInfoController.text.trim() 
            : null,
        confidence: _confidence,
      );

      loggingService.info('Entity updated successfully', screen: 'MemoriesScreen', data: {
        'entityId': widget.entity.id,
      });

      widget.onEntityUpdated();
      Navigator.pop(context);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Entity updated successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'MemoriesScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to update entity: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit Entity'),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _userController,
                decoration: const InputDecoration(
                  labelText: 'User Name',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a user name';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              DropdownButtonFormField<String>(
                value: _selectedEntityType,
                decoration: const InputDecoration(
                  labelText: 'Entity Type',
                  border: OutlineInputBorder(),
                ),
                items: AppConstants.entityTypes.map((type) => DropdownMenuItem<String>(
                  value: type,
                  child: Text(AppConstants.entityTypeDisplayNames[type] ?? type),
                )).toList(),
                onChanged: (value) {
                  setState(() {
                    _selectedEntityType = value!;
                  });
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _entityTextController,
                decoration: const InputDecoration(
                  labelText: 'Entity Text',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter entity text';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _contextInfoController,
                decoration: const InputDecoration(
                  labelText: 'Context Info (Optional)',
                  border: OutlineInputBorder(),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  const Text('Confidence: '),
                  Expanded(
                    child: Slider(
                      value: _confidence,
                      min: 0.0,
                      max: 1.0,
                      divisions: 10,
                      label: '${(_confidence * 100).toStringAsFixed(0)}%',
                      onChanged: (value) {
                        setState(() {
                          _confidence = value;
                        });
                      },
                    ),
                  ),
                  Text('${(_confidence * 100).toStringAsFixed(0)}%'),
                ],
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _updateEntity,
          child: const Text('Update'),
        ),
      ],
    );
  }
}
