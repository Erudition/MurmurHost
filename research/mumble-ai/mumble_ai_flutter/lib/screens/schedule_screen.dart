import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../services/logging_service.dart';
import '../models/schedule_event.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class ScheduleScreen extends StatefulWidget {
  const ScheduleScreen({Key? key}) : super(key: key);

  @override
  State<ScheduleScreen> createState() => _ScheduleScreenState();
}

class _ScheduleScreenState extends State<ScheduleScreen> {
  List<ScheduleEvent> _events = [];
  List<String> _users = [];
  bool _isLoading = true;
  String? _errorMessage;
  String? _selectedUser;
  bool _showCalendarView = false;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('ScheduleScreen', 'initState');
    
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      await Future.wait([
        _loadEvents(),
        _loadUsers(),
      ]);

      setState(() {
        _isLoading = false;
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'ScheduleScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load data: ${e.toString()}';
      });
    }
  }

  Future<void> _loadEvents() async {
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

      final response = await apiService.get(
        AppConstants.scheduleEndpoint,
        queryParameters: queryParams,
      );

      // Handle both new wrapped format and legacy array format
      List<dynamic> eventsList;
      if (response.data is Map<String, dynamic>) {
        // New wrapped format: {"success": true, "data": {"events": [...], "pagination": {...}}}
        final data = response.data['data'];
        eventsList = data['events'] as List;
      } else if (response.data is List) {
        // Legacy format: [...]
        eventsList = response.data as List;
      } else {
        throw Exception('Unexpected response format: expected Map or List, got ${response.data.runtimeType}');
      }

      final events = eventsList
          .map((json) => ScheduleEvent.fromJson(json))
          .toList();

      // Sort events by date
      events.sort((a, b) {
        final aDateTime = _getEventDateTime(a);
        final bDateTime = _getEventDateTime(b);
        return aDateTime.compareTo(bDateTime);
      });

      setState(() {
        _events = events;
      });
      
      loggingService.info('Schedule events loaded successfully', screen: 'ScheduleScreen', data: {
        'count': events.length,
        'user': currentUser,
      });
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'ScheduleScreen');
      throw Exception('Failed to load events: $e');
    }
  }

  Future<void> _loadUsers() async {
    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final response = await apiService.get(AppConstants.scheduleUsersEndpoint);
      
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
      loggingService.logException(e, stackTrace, screen: 'ScheduleScreen');
      
      setState(() {
        _users = [];
      });
    }
  }

  Future<void> _deleteEvent(int eventId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Event'),
        content: const Text('Are you sure you want to delete this event?'),
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
        
        loggingService.logUserAction('Delete Event', screen: 'ScheduleScreen', data: {
          'eventId': eventId,
        });
        
        await apiService.delete('${AppConstants.scheduleEndpoint}/$eventId');
        
        setState(() {
          _events.removeWhere((event) => event.id == eventId);
        });

        loggingService.info('Event deleted successfully', screen: 'ScheduleScreen', data: {
          'eventId': eventId,
        });

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Event deleted successfully'),
              backgroundColor: AppTheme.successColor,
            ),
          );
        }
      } catch (e, stackTrace) {
        final loggingService = Provider.of<LoggingService>(context, listen: false);
        loggingService.logException(e, stackTrace, screen: 'ScheduleScreen');
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to delete event: ${e.toString()}'),
              backgroundColor: AppTheme.errorColor,
            ),
          );
        }
      }
    }
  }

  void _showAddEventDialog() {
    showDialog(
      context: context,
      builder: (context) => _AddEventDialog(
        users: _users,
        onEventAdded: () {
          _loadEvents();
        },
      ),
    );
  }

  void _showEditEventDialog(ScheduleEvent event) {
    showDialog(
      context: context,
      builder: (context) => _EditEventDialog(
        event: event,
        users: _users,
        onEventUpdated: () {
          _loadEvents();
        },
      ),
    );
  }

  Color _getImportanceColor(int importance) {
    if (importance >= 8) return AppTheme.errorColor;
    if (importance >= 5) return AppTheme.warningColor;
    return AppTheme.primaryColor;
  }

  static DateTime _getEventDateTime(ScheduleEvent event) {
    if (event.eventDate == null) return DateTime.now();
    
    try {
      final date = DateTime.parse(event.eventDate!);
      if (event.eventTime != null && event.eventTime!.isNotEmpty) {
        final timeParts = event.eventTime!.split(':');
        if (timeParts.length >= 2) {
          final hour = int.parse(timeParts[0]);
          final minute = int.parse(timeParts[1]);
          return DateTime(date.year, date.month, date.day, hour, minute);
        }
      }
      return date;
    } catch (e) {
      return DateTime.now();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Schedule'),
        actions: [
          IconButton(
            icon: const Icon(Icons.chat),
            onPressed: () {
              Navigator.pushNamed(context, '/chat');
            },
            tooltip: 'Ask AI about your schedule',
          ),
          IconButton(
            icon: Icon(_showCalendarView ? Icons.list : Icons.calendar_today),
            onPressed: () {
              setState(() {
                _showCalendarView = !_showCalendarView;
              });
            },
            tooltip: _showCalendarView ? 'List View' : 'Calendar View',
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading schedule...')
          : _errorMessage != null
              ? _buildErrorState()
              : _events.isEmpty
                  ? _buildEmptyState()
                  : Column(
                      children: [
                        _buildFilters(),
                        Expanded(
                          child: RefreshIndicator(
                            onRefresh: _loadEvents,
                            child: _showCalendarView
                                ? _buildCalendarView()
                                : _buildListView(),
                          ),
                        ),
                      ],
                    ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddEventDialog,
        child: const Icon(Icons.add),
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
              'Error Loading Schedule',
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
              Icons.calendar_today_outlined,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: AppTheme.spacingM),
            Text(
              'No Events',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spacingS),
            Text(
              'Schedule events will appear here',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppTheme.spacingL),
            ElevatedButton.icon(
              onPressed: _showAddEventDialog,
              icon: const Icon(Icons.add),
              label: const Text('Add Event'),
            ),
            const SizedBox(height: AppTheme.spacingM),
            TextButton.icon(
              onPressed: () {
                Navigator.pushNamed(context, '/chat');
              },
              icon: const Icon(Icons.chat),
              label: const Text('Ask AI about your schedule'),
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
                _loadEvents();
              },
            ),
          ),
          const SizedBox(width: AppTheme.spacingM),
          Expanded(
            child: Text(
              '${_events.length} events',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildListView() {
    return ListView.builder(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      itemCount: _events.length,
      itemBuilder: (context, index) {
        final event = _events[index];
        return _buildEventCard(event);
      },
    );
  }

  Widget _buildCalendarView() {
    // Group events by date
    final eventsByDate = <String, List<ScheduleEvent>>{};
    for (final event in _events) {
      final eventDateTime = _getEventDateTime(event);
      final dateKey = DateFormat('yyyy-MM-dd').format(eventDateTime);
      eventsByDate.putIfAbsent(dateKey, () => []).add(event);
    }

    return ListView.builder(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      itemCount: eventsByDate.length,
      itemBuilder: (context, index) {
        final dateKey = eventsByDate.keys.elementAt(index);
        final dateEvents = eventsByDate[dateKey]!;
        final date = DateTime.parse(dateKey);
        
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AppTheme.spacingS),
              child: Text(
                DateFormat('EEEE, MMMM d, y').format(date),
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primaryColor,
                ),
              ),
            ),
            ...dateEvents.map((event) => Padding(
              padding: const EdgeInsets.only(bottom: AppTheme.spacingS),
              child: _buildEventCard(event),
            )),
            const SizedBox(height: AppTheme.spacingM),
          ],
        );
      },
    );
  }

  Widget _buildEventCard(ScheduleEvent event) {
    final eventDateTime = _getEventDateTime(event);
    final isPast = eventDateTime.isBefore(DateTime.now());
    
    return Card(
      child: InkWell(
        onTap: () => _showEditEventDialog(event),
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
                      color: _getImportanceColor(event.importance).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(AppTheme.radiusS),
                      border: Border.all(
                        color: _getImportanceColor(event.importance).withOpacity(0.3),
                      ),
                    ),
                    child: Text(
                      event.importanceLevel,
                      style: TextStyle(
                        color: _getImportanceColor(event.importance),
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingS),
                  if (isPast)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppTheme.spacingS,
                        vertical: AppTheme.spacingXS,
                      ),
                      decoration: BoxDecoration(
                        color: AppTheme.textTertiary.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(AppTheme.radiusS),
                        border: Border.all(
                          color: AppTheme.textTertiary.withOpacity(0.3),
                        ),
                      ),
                      child: const Text(
                        'Past',
                        style: TextStyle(
                          color: AppTheme.textTertiary,
                          fontWeight: FontWeight.w600,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  const Spacer(),
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      if (value == 'edit') {
                        _showEditEventDialog(event);
                      } else if (value == 'delete') {
                        _deleteEvent(event.id);
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
                event.title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
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
                  Text(
                    event.userName,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondary,
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingM),
                  const Icon(
                    Icons.access_time,
                    size: 16,
                    color: AppTheme.textSecondary,
                  ),
                  const SizedBox(width: AppTheme.spacingXS),
                  Text(
                    DateFormat('MMM d, h:mm a').format(eventDateTime),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
              if (event.description != null && event.description!.isNotEmpty) ...[
                const SizedBox(height: AppTheme.spacingS),
                Text(
                  event.description!,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              if (event.reminderEnabled) ...[
                const SizedBox(height: AppTheme.spacingS),
                Row(
                  children: [
                    const Icon(
                      Icons.email,
                      size: 16,
                      color: AppTheme.infoColor,
                    ),
                    const SizedBox(width: AppTheme.spacingXS),
                    Text(
                      'Email reminder: ${AppConstants.reminderMinutesDisplayNames[event.reminderMinutes] ?? '${event.reminderMinutes} minutes'}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTheme.infoColor,
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _AddEventDialog extends StatefulWidget {
  final List<String> users;
  final VoidCallback onEventAdded;

  const _AddEventDialog({
    Key? key,
    required this.users,
    required this.onEventAdded,
  }) : super(key: key);

  @override
  State<_AddEventDialog> createState() => _AddEventDialogState();
}

class _AddEventDialogState extends State<_AddEventDialog> {
  final _formKey = GlobalKey<FormState>();
  final _userController = TextEditingController();
  final _titleController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _recipientEmailController = TextEditingController();
  
  DateTime _selectedDate = DateTime.now();
  TimeOfDay _selectedTime = TimeOfDay.now();
  int _importance = 5;
  bool _emailReminder = false;
  int _reminderMinutes = 60;

  @override
  void dispose() {
    _userController.dispose();
    _titleController.dispose();
    _descriptionController.dispose();
    _recipientEmailController.dispose();
    super.dispose();
  }

  Future<void> _selectDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (date != null) {
      setState(() {
        _selectedDate = date;
      });
    }
  }

  Future<void> _selectTime() async {
    final time = await showTimePicker(
      context: context,
      initialTime: _selectedTime,
    );
    if (time != null) {
      setState(() {
        _selectedTime = time;
      });
    }
  }

  Future<void> _saveEvent() async {
    if (!_formKey.currentState!.validate()) return;

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final dateTime = DateTime(
        _selectedDate.year,
        _selectedDate.month,
        _selectedDate.day,
        _selectedTime.hour,
        _selectedTime.minute,
      );

      loggingService.logUserAction('Add Event', screen: 'ScheduleScreen', data: {
        'user': _userController.text.trim(),
        'title': _titleController.text.trim(),
        'importance': _importance,
        'emailReminder': _emailReminder,
      });

      await apiService.post(AppConstants.scheduleEndpoint, data: {
        'user_name': _userController.text.trim(),
        'title': _titleController.text.trim(),
        'description': _descriptionController.text.trim(),
        'date_time': dateTime.toIso8601String(),
        'importance': _importance,
        'email_reminder': _emailReminder,
        'reminder_minutes': _reminderMinutes,
        'recipient_email': _recipientEmailController.text.trim(),
      });

      loggingService.info('Event added successfully', screen: 'ScheduleScreen');

      widget.onEventAdded();
      Navigator.pop(context);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Event added successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'ScheduleScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to add event: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Event'),
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
              TextFormField(
                controller: _titleController,
                decoration: const InputDecoration(
                  labelText: 'Title',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a title';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _descriptionController,
                decoration: const InputDecoration(
                  labelText: 'Description',
                  border: OutlineInputBorder(),
                ),
                maxLines: 3,
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  Expanded(
                    child: InkWell(
                      onTap: _selectDate,
                      child: InputDecorator(
                        decoration: const InputDecoration(
                          labelText: 'Date',
                          border: OutlineInputBorder(),
                        ),
                        child: Text(DateFormat('MMM d, y').format(_selectedDate)),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingM),
                  Expanded(
                    child: InkWell(
                      onTap: _selectTime,
                      child: InputDecorator(
                        decoration: const InputDecoration(
                          labelText: 'Time',
                          border: OutlineInputBorder(),
                        ),
                        child: Text(_selectedTime.format(context)),
                      ),
                    ),
                  ),
                ],
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
              const SizedBox(height: AppTheme.spacingM),
              SwitchListTile(
                title: const Text('Email Reminder'),
                value: _emailReminder,
                onChanged: (value) {
                  setState(() {
                    _emailReminder = value;
                  });
                },
              ),
              if (_emailReminder) ...[
                DropdownButtonFormField<int>(
                  value: _reminderMinutes,
                  decoration: const InputDecoration(
                    labelText: 'Reminder Time',
                    border: OutlineInputBorder(),
                  ),
                  items: AppConstants.reminderMinutesOptions.map((minutes) => DropdownMenuItem<int>(
                    value: minutes,
                    child: Text(AppConstants.reminderMinutesDisplayNames[minutes] ?? '$minutes minutes'),
                  )).toList(),
                  onChanged: (value) {
                    setState(() {
                      _reminderMinutes = value!;
                    });
                  },
                ),
                const SizedBox(height: AppTheme.spacingM),
                TextFormField(
                  controller: _recipientEmailController,
                  decoration: const InputDecoration(
                    labelText: 'Recipient Email',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.emailAddress,
                ),
              ],
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
          onPressed: _saveEvent,
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class _EditEventDialog extends StatefulWidget {
  final ScheduleEvent event;
  final List<String> users;
  final VoidCallback onEventUpdated;

  const _EditEventDialog({
    Key? key,
    required this.event,
    required this.users,
    required this.onEventUpdated,
  }) : super(key: key);

  @override
  State<_EditEventDialog> createState() => _EditEventDialogState();
}

class _EditEventDialogState extends State<_EditEventDialog> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _userController;
  late TextEditingController _titleController;
  late TextEditingController _descriptionController;
  late TextEditingController _recipientEmailController;
  
  late DateTime _selectedDate;
  late TimeOfDay _selectedTime;
  late int _importance;
  late bool _emailReminder;
  late int _reminderMinutes;

  @override
  void initState() {
    super.initState();
    _userController = TextEditingController(text: widget.event.userName);
    _titleController = TextEditingController(text: widget.event.title);
    _descriptionController = TextEditingController(text: widget.event.description ?? '');
    _recipientEmailController = TextEditingController(text: widget.event.recipientEmail ?? '');
    
    final eventDateTime = _ScheduleScreenState._getEventDateTime(widget.event);
    _selectedDate = eventDateTime;
    _selectedTime = TimeOfDay.fromDateTime(eventDateTime);
    _importance = widget.event.importance;
    _emailReminder = widget.event.reminderEnabled;
    _reminderMinutes = widget.event.reminderMinutes;
  }

  @override
  void dispose() {
    _userController.dispose();
    _titleController.dispose();
    _descriptionController.dispose();
    _recipientEmailController.dispose();
    super.dispose();
  }

  Future<void> _selectDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (date != null) {
      setState(() {
        _selectedDate = date;
      });
    }
  }

  Future<void> _selectTime() async {
    final time = await showTimePicker(
      context: context,
      initialTime: _selectedTime,
    );
    if (time != null) {
      setState(() {
        _selectedTime = time;
      });
    }
  }

  Future<void> _updateEvent() async {
    if (!_formKey.currentState!.validate()) return;

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final dateTime = DateTime(
        _selectedDate.year,
        _selectedDate.month,
        _selectedDate.day,
        _selectedTime.hour,
        _selectedTime.minute,
      );

      loggingService.logUserAction('Update Event', screen: 'ScheduleScreen', data: {
        'eventId': widget.event.id,
        'user': _userController.text.trim(),
        'title': _titleController.text.trim(),
        'importance': _importance,
      });

      await apiService.put('${AppConstants.scheduleEndpoint}/${widget.event.id}', data: {
        'user_name': _userController.text.trim(),
        'title': _titleController.text.trim(),
        'description': _descriptionController.text.trim(),
        'date_time': dateTime.toIso8601String(),
        'importance': _importance,
        'email_reminder': _emailReminder,
        'reminder_minutes': _reminderMinutes,
        'recipient_email': _recipientEmailController.text.trim(),
      });

      loggingService.info('Event updated successfully', screen: 'ScheduleScreen', data: {
        'eventId': widget.event.id,
      });

      widget.onEventUpdated();
      Navigator.pop(context);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Event updated successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'ScheduleScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to update event: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit Event'),
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
              TextFormField(
                controller: _titleController,
                decoration: const InputDecoration(
                  labelText: 'Title',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a title';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _descriptionController,
                decoration: const InputDecoration(
                  labelText: 'Description',
                  border: OutlineInputBorder(),
                ),
                maxLines: 3,
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  Expanded(
                    child: InkWell(
                      onTap: _selectDate,
                      child: InputDecorator(
                        decoration: const InputDecoration(
                          labelText: 'Date',
                          border: OutlineInputBorder(),
                        ),
                        child: Text(DateFormat('MMM d, y').format(_selectedDate)),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingM),
                  Expanded(
                    child: InkWell(
                      onTap: _selectTime,
                      child: InputDecorator(
                        decoration: const InputDecoration(
                          labelText: 'Time',
                          border: OutlineInputBorder(),
                        ),
                        child: Text(_selectedTime.format(context)),
                      ),
                    ),
                  ),
                ],
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
              const SizedBox(height: AppTheme.spacingM),
              SwitchListTile(
                title: const Text('Email Reminder'),
                value: _emailReminder,
                onChanged: (value) {
                  setState(() {
                    _emailReminder = value;
                  });
                },
              ),
              if (_emailReminder) ...[
                DropdownButtonFormField<int>(
                  value: _reminderMinutes,
                  decoration: const InputDecoration(
                    labelText: 'Reminder Time',
                    border: OutlineInputBorder(),
                  ),
                  items: AppConstants.reminderMinutesOptions.map((minutes) => DropdownMenuItem<int>(
                    value: minutes,
                    child: Text(AppConstants.reminderMinutesDisplayNames[minutes] ?? '$minutes minutes'),
                  )).toList(),
                  onChanged: (value) {
                    setState(() {
                      _reminderMinutes = value!;
                    });
                  },
                ),
                const SizedBox(height: AppTheme.spacingM),
                TextFormField(
                  controller: _recipientEmailController,
                  decoration: const InputDecoration(
                    labelText: 'Recipient Email',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.emailAddress,
                ),
              ],
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
          onPressed: _updateEvent,
          child: const Text('Update'),
        ),
      ],
    );
  }
}
