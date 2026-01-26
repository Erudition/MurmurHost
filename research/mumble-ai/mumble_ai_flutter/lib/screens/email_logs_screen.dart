import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../models/email_log.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class EmailLogsScreen extends StatefulWidget {
  const EmailLogsScreen({Key? key}) : super(key: key);

  @override
  State<EmailLogsScreen> createState() => _EmailLogsScreenState();
}

class _EmailLogsScreenState extends State<EmailLogsScreen> {
  List<EmailLog> _emailLogs = [];
  bool _isLoading = true;
  String? _errorMessage;
  String? _selectedDirection;
  String? _selectedType;
  String? _selectedStatus;
  int _currentPage = 1;
  bool _hasMore = true;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('EmailLogsScreen', 'initState');
    
    _loadEmailLogs();
  }

  Future<void> _loadEmailLogs({bool refresh = false}) async {
    if (refresh) {
      setState(() {
        _currentPage = 1;
        _hasMore = true;
        _emailLogs.clear();
      });
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final queryParams = <String, dynamic>{
        'page': _currentPage,
        'limit': 50,
      };

      if (_selectedDirection != null) {
        queryParams['direction'] = _selectedDirection;
      }
      if (_selectedType != null) {
        queryParams['type'] = _selectedType;
      }
      if (_selectedStatus != null) {
        queryParams['status'] = _selectedStatus;
      }

      final response = await apiService.get(
        AppConstants.emailLogsEndpoint,
        queryParameters: queryParams,
      );

      final newLogs = (response.data['logs'] as List)
          .map((json) => EmailLog.fromJson(Map<String, dynamic>.from(json)))
          .toList();

      setState(() {
        if (refresh) {
          _emailLogs = newLogs;
        } else {
          _emailLogs.addAll(newLogs);
        }
        _hasMore = newLogs.length == 50;
        _isLoading = false;
      });
      
      loggingService.info('Email logs loaded successfully', screen: 'EmailLogsScreen', data: {
        'count': newLogs.length,
        'page': _currentPage,
        'filters': queryParams,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'EmailLogsScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load email logs: ${e.toString()}';
      });
    }
  }

  Future<void> _loadMore() async {
    if (!_hasMore || _isLoading) return;

    setState(() {
      _currentPage++;
    });

    await _loadEmailLogs();
  }

  Future<void> _retryEmail(int logId) async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Retry Email', screen: 'EmailLogsScreen', data: {
        'logId': logId,
      });
      
      await apiService.post('${AppConstants.retryEmailEndpoint}/$logId', data: {});

      loggingService.info('Email retry initiated successfully', screen: 'EmailLogsScreen', data: {
        'logId': logId,
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Email retry initiated successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }

      // Refresh the logs to show updated status
      _loadEmailLogs(refresh: true);
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'EmailLogsScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to retry email: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  void _showEmailDetails(EmailLog emailLog) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Email Details - ${emailLog.emailType}'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildDetailRow('Direction', emailLog.direction),
              _buildDetailRow('Type', emailLog.emailType),
              _buildDetailRow('Status', emailLog.status),
              _buildDetailRow('From', emailLog.fromEmail),
              _buildDetailRow('To', emailLog.toEmail),
              _buildDetailRow('Subject', emailLog.subject),
              _buildDetailRow('Timestamp', emailLog.timestamp ?? 'Unknown'),
              if (emailLog.errorMessage != null) ...[
                const SizedBox(height: AppTheme.spacingM),
                Text(
                  'Error Message:',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: AppTheme.spacingS),
                Container(
                  padding: const EdgeInsets.all(AppTheme.spacingM),
                  decoration: BoxDecoration(
                    color: AppTheme.errorColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(AppTheme.radiusM),
                    border: Border.all(
                      color: AppTheme.errorColor.withOpacity(0.3),
                    ),
                  ),
                  child: Text(
                    emailLog.errorMessage!,
                    style: const TextStyle(
                      color: AppTheme.errorColor,
                      fontFamily: 'monospace',
                    ),
                  ),
                ),
              ],
              if (emailLog.fullBody != null && emailLog.fullBody!.isNotEmpty) ...[
                const SizedBox(height: AppTheme.spacingM),
                Text(
                  'Content:',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: AppTheme.spacingS),
                Container(
                  padding: const EdgeInsets.all(AppTheme.spacingM),
                  decoration: BoxDecoration(
                    color: AppTheme.backgroundColor,
                    borderRadius: BorderRadius.circular(AppTheme.radiusM),
                    border: Border.all(color: AppTheme.borderColor),
                  ),
                  child: Text(
                    emailLog.fullBody!,
                    style: const TextStyle(fontFamily: 'monospace'),
                  ),
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          if (emailLog.status == 'error')
            ElevatedButton(
              onPressed: () {
                Navigator.pop(context);
                _retryEmail(emailLog.id);
              },
              style: ElevatedButton.styleFrom(primary: AppTheme.warningColor),
              child: const Text('Retry'),
            ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppTheme.spacingS),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              '$label:',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary,
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

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'success':
        return AppTheme.successColor;
      case 'error':
        return AppTheme.errorColor;
      default:
        return AppTheme.textSecondary;
    }
  }

  IconData _getDirectionIcon(String direction) {
    switch (direction.toLowerCase()) {
      case 'sent':
        return Icons.send;
      case 'received':
        return Icons.inbox;
      default:
        return Icons.email;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Email Logs'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _loadEmailLogs(refresh: true),
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _isLoading && _emailLogs.isEmpty
          ? const LoadingIndicator(message: 'Loading email logs...')
          : _errorMessage != null
              ? _buildErrorState()
              : _emailLogs.isEmpty
                  ? _buildEmptyState()
                  : Column(
                      children: [
                        _buildFilters(),
                        Expanded(
                          child: RefreshIndicator(
                            onRefresh: () => _loadEmailLogs(refresh: true),
                            child: ListView.builder(
                              padding: const EdgeInsets.all(AppTheme.spacingM),
                              itemCount: _emailLogs.length + (_hasMore ? 1 : 0),
                              itemBuilder: (context, index) {
                                if (index == _emailLogs.length) {
                                  // Load more indicator
                                  if (_hasMore) {
                                    _loadMore();
                                    return const Padding(
                                      padding: EdgeInsets.all(AppTheme.spacingM),
                                      child: Center(
                                        child: CircularProgressIndicator(),
                                      ),
                                    );
                                  }
                                  return const SizedBox.shrink();
                                }

                                final emailLog = _emailLogs[index];
                                return _buildEmailLogCard(emailLog);
                              },
                            ),
                          ),
                        ),
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
              'Error Loading Email Logs',
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
              onPressed: () => _loadEmailLogs(refresh: true),
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
              Icons.email_outlined,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'No Email Logs',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Email logs will appear here when emails are sent or received',
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

  Widget _buildFilters() {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: const Border(
          bottom: BorderSide(color: AppTheme.borderColor),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _selectedDirection,
                  decoration: const InputDecoration(
                    labelText: 'Direction',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: AppTheme.spacingM,
                      vertical: AppTheme.spacingS,
                    ),
                  ),
                  items: [
                    const DropdownMenuItem<String>(
                      value: null,
                      child: Text('All Directions'),
                    ),
                    ...AppConstants.emailDirections.map((direction) => DropdownMenuItem<String>(
                      value: direction,
                      child: Text(direction.toUpperCase()),
                    )),
                  ],
                  onChanged: (value) {
                    setState(() {
                      _selectedDirection = value;
                    });
                    _loadEmailLogs(refresh: true);
                  },
                ),
              ),
              const SizedBox(width: AppTheme.spacingM),
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _selectedType,
                  decoration: const InputDecoration(
                    labelText: 'Type',
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
                    ...AppConstants.emailTypes.map((type) => DropdownMenuItem<String>(
                      value: type,
                      child: Text(type.toUpperCase()),
                    )),
                  ],
                  onChanged: (value) {
                    setState(() {
                      _selectedType = value;
                    });
                    _loadEmailLogs(refresh: true);
                  },
                ),
              ),
            ],
          ),
          const SizedBox(height: AppTheme.spacingM),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _selectedStatus,
                  decoration: const InputDecoration(
                    labelText: 'Status',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: AppTheme.spacingM,
                      vertical: AppTheme.spacingS,
                    ),
                  ),
                  items: [
                    const DropdownMenuItem<String>(
                      value: null,
                      child: Text('All Statuses'),
                    ),
                    ...AppConstants.emailStatuses.map((status) => DropdownMenuItem<String>(
                      value: status,
                      child: Text(status.toUpperCase()),
                    )),
                  ],
                  onChanged: (value) {
                    setState(() {
                      _selectedStatus = value;
                    });
                    _loadEmailLogs(refresh: true);
                  },
                ),
              ),
              const SizedBox(width: AppTheme.spacingM),
              Expanded(
                child: Text(
                  '${_emailLogs.length} logs',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEmailLogCard(EmailLog emailLog) {
    return Card(
      margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
      child: InkWell(
        onTap: () => _showEmailDetails(emailLog),
        borderRadius: BorderRadius.circular(AppTheme.radiusL),
        child: Padding(
          padding: const EdgeInsets.all(AppTheme.spacingM),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    _getDirectionIcon(emailLog.direction),
                    size: 20,
                    color: AppTheme.textSecondary,
                  ),
                  const SizedBox(width: AppTheme.spacingS),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppTheme.spacingS,
                      vertical: AppTheme.spacingXS,
                    ),
                    decoration: BoxDecoration(
                      color: _getStatusColor(emailLog.status).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(AppTheme.radiusS),
                      border: Border.all(
                        color: _getStatusColor(emailLog.status).withOpacity(0.3),
                      ),
                    ),
                    child: Text(
                      emailLog.status.toUpperCase(),
                      style: TextStyle(
                        color: _getStatusColor(emailLog.status),
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
                      emailLog.emailType.toUpperCase(),
                      style: const TextStyle(
                        color: AppTheme.primaryColor,
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const Spacer(),
                  if (emailLog.status == 'error')
                    IconButton(
                      icon: const Icon(Icons.refresh, color: AppTheme.warningColor),
                      onPressed: () => _retryEmail(emailLog.id),
                      tooltip: 'Retry Email',
                    ),
                ],
              ),
              const SizedBox(height: AppTheme.spacingS),
              Text(
                emailLog.subject,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: AppTheme.spacingXS),
              Row(
                children: [
                  const Icon(
                    Icons.person,
                    size: 16,
                    color: AppTheme.textSecondary,
                  ),
                  const SizedBox(width: AppTheme.spacingXS),
                  Expanded(
                    child: Text(
                      '${emailLog.fromEmail} → ${emailLog.toEmail}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTheme.textSecondary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppTheme.spacingXS),
              Row(
                children: [
                  const Icon(
                    Icons.access_time,
                    size: 16,
                    color: AppTheme.textSecondary,
                  ),
                  const SizedBox(width: AppTheme.spacingXS),
                  Text(
                    emailLog.timestamp ?? 'Unknown',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
              if (emailLog.errorMessage != null) ...[
                const SizedBox(height: AppTheme.spacingS),
                Container(
                  padding: const EdgeInsets.all(AppTheme.spacingS),
                  decoration: BoxDecoration(
                    color: AppTheme.errorColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(AppTheme.radiusS),
                    border: Border.all(
                      color: AppTheme.errorColor.withOpacity(0.3),
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.error_outline,
                        size: 16,
                        color: AppTheme.errorColor,
                      ),
                      const SizedBox(width: AppTheme.spacingXS),
                      Expanded(
                        child: Text(
                          emailLog.errorMessage!,
                          style: const TextStyle(
                            color: AppTheme.errorColor,
                            fontSize: 12,
                          ),
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
}
