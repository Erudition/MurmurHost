import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../services/logging_service.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';
import 'main_scaffold.dart';

class UserSelectionScreen extends StatefulWidget {
  const UserSelectionScreen({Key? key}) : super(key: key);

  @override
  State<UserSelectionScreen> createState() => _UserSelectionScreenState();
}

class _UserSelectionScreenState extends State<UserSelectionScreen> {
  List<String> _users = [];
  bool _isLoading = true;
  String? _errorMessage;
  String? _selectedUser;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('UserSelectionScreen', 'initState');
    
    _loadUsers();
  }

  Future<void> _loadUsers() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      final response = await apiService.get(AppConstants.usersEndpoint);
      
      loggingService.debug('Users response type: ${response.data.runtimeType}', screen: 'UserSelectionScreen');
      loggingService.debug('Users response data: ${response.data}', screen: 'UserSelectionScreen');
      
      // Handle the response data - supports both formats for robustness
      List<String> users = [];
      
      if (response.data is Map<String, dynamic>) {
        // New format: {"users": ["user1", "user2"]}
        final usersData = response.data['users'];
        if (usersData is List) {
          users = (usersData as List).map((item) => item.toString()).toList();
        } else {
          throw Exception('Invalid response format: users field is not a List');
        }
      } else if (response.data is List) {
        // Legacy format: ["user1", "user2"] (for backwards compatibility)
        users = (response.data as List).map((item) => item.toString()).toList();
      } else {
        loggingService.error('Unexpected response type for users endpoint', screen: 'UserSelectionScreen');
        throw Exception('Invalid response format: expected Map or List, got ${response.data.runtimeType}');
      }
      
      setState(() {
        _users = users;
        _isLoading = false;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'UserSelectionScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load users: ${e.toString()}';
      });
    }
  }

  Future<void> _selectUser(String user) async {
    try {
      final storageService = Provider.of<StorageService>(context, listen: false);
      await storageService.setSelectedUser(user);
      
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.info('User selected: $user', screen: 'UserSelectionScreen');
      
      if (mounted) {
        Navigator.pushReplacementNamed(context, '/dashboard');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save user selection: ${e.toString()}'),
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
        title: const Text('Select User'),
        automaticallyImplyLeading: false, // Remove back button
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading users...')
          : _errorMessage != null
              ? _buildErrorState()
              : _users.isEmpty
                  ? _buildEmptyState()
                  : _buildUserList(),
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
              'Error Loading Users',
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
              onPressed: _loadUsers,
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
              Icons.person_outline,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'No Users Found',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'No users have been detected in the system yet. Try again later or check your server connection.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppTheme.spacingL),
            ElevatedButton.icon(
              onPressed: _loadUsers,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUserList() {
    return Padding(
      padding: const EdgeInsets.all(AppTheme.spacingL),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Select Your User',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppTheme.spacingS),
          Text(
            'Choose which user you are to see your personalized data:',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: AppTheme.spacingL),
          Expanded(
            child: ListView.builder(
              itemCount: _users.length,
              itemBuilder: (context, index) {
                final user = _users[index];
                final isSelected = _selectedUser == user;
                
                return Card(
                  margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
                  child: InkWell(
                    onTap: () {
                      setState(() {
                        _selectedUser = user;
                      });
                    },
                    borderRadius: BorderRadius.circular(AppTheme.radiusL),
                    child: Container(
                      padding: const EdgeInsets.all(AppTheme.spacingM),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(AppTheme.radiusL),
                        border: isSelected 
                            ? Border.all(color: AppTheme.primaryColor, width: 2)
                            : null,
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 48,
                            height: 48,
                            decoration: BoxDecoration(
                              color: isSelected 
                                  ? AppTheme.primaryColor 
                                  : AppTheme.backgroundColor,
                              borderRadius: BorderRadius.circular(AppTheme.radiusL),
                            ),
                            child: Icon(
                              Icons.person,
                              color: isSelected 
                                  ? Colors.white 
                                  : AppTheme.textSecondary,
                              size: 24,
                            ),
                          ),
                          const SizedBox(width: AppTheme.spacingM),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  user,
                                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: isSelected 
                                        ? AppTheme.primaryColor 
                                        : null,
                                  ),
                                ),
                                const SizedBox(height: AppTheme.spacingXS),
                                Text(
                                  'View memories, schedule, and conversations',
                                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          if (isSelected)
                            const Icon(
                              Icons.check_circle,
                              color: AppTheme.primaryColor,
                              size: 24,
                            ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: AppTheme.spacingL),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _selectedUser != null ? () => _selectUser(_selectedUser!) : null,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: AppTheme.spacingM),
              ),
              child: const Text('Continue'),
            ),
          ),
        ],
      ),
    );
  }
}
