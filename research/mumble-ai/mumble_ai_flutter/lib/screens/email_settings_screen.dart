import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../widgets/loading_indicator.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class EmailSettingsScreen extends StatefulWidget {
  const EmailSettingsScreen({Key? key}) : super(key: key);

  @override
  State<EmailSettingsScreen> createState() => _EmailSettingsScreenState();
}

class _EmailSettingsScreenState extends State<EmailSettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  
  // SMTP Configuration
  final _smtpHostController = TextEditingController();
  final _smtpPortController = TextEditingController();
  final _smtpUsernameController = TextEditingController();
  final _smtpPasswordController = TextEditingController();
  final _fromEmailController = TextEditingController();
  final _recipientEmailController = TextEditingController();
  
  // Daily Summary
  final _summaryTimeController = TextEditingController();
  
  // IMAP Configuration
  final _imapHostController = TextEditingController();
  final _imapPortController = TextEditingController();
  final _imapUsernameController = TextEditingController();
  final _imapPasswordController = TextEditingController();
  final _mailboxNameController = TextEditingController();
  final _checkIntervalController = TextEditingController();
  
  // Auto-reply
  final _replySignatureController = TextEditingController();
  
  // Toggles
  bool _smtpTls = false;
  bool _smtpSsl = false;
  bool _dailySummaryEnabled = false;
  bool _imapEnabled = false;
  bool _imapSsl = false;
  bool _autoReplyEnabled = false;
  
  // Dropdowns
  String _selectedTimezone = 'America/New_York';
  int _checkInterval = 5;
  
  bool _isLoading = true;
  bool _isSaving = false;
  bool _isGeneratingSignature = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    
    // Log screen entry
    final loggingService = Provider.of<LoggingService>(context, listen: false);
    loggingService.logScreenLifecycle('EmailSettingsScreen', 'initState');
    
    _loadEmailSettings();
  }

  @override
  void dispose() {
    _smtpHostController.dispose();
    _smtpPortController.dispose();
    _smtpUsernameController.dispose();
    _smtpPasswordController.dispose();
    _fromEmailController.dispose();
    _recipientEmailController.dispose();
    _summaryTimeController.dispose();
    _imapHostController.dispose();
    _imapPortController.dispose();
    _imapUsernameController.dispose();
    _imapPasswordController.dispose();
    _mailboxNameController.dispose();
    _checkIntervalController.dispose();
    _replySignatureController.dispose();
    super.dispose();
  }

  Future<void> _loadEmailSettings() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      final response = await apiService.get(AppConstants.emailSettingsEndpoint);
      final data = response.data;

      setState(() {
        // SMTP Configuration
        _smtpHostController.text = data['smtp_host'] ?? '';
        _smtpPortController.text = data['smtp_port']?.toString() ?? '587';
        _smtpUsernameController.text = data['smtp_username'] ?? '';
        _smtpPasswordController.text = data['smtp_password'] ?? '';
        _fromEmailController.text = data['from_email'] ?? '';
        _recipientEmailController.text = data['recipient_email'] ?? '';
        _smtpTls = data['smtp_tls'] ?? false;
        _smtpSsl = data['smtp_ssl'] ?? false;

        // Daily Summary
        _dailySummaryEnabled = data['daily_summary_enabled'] ?? false;
        _summaryTimeController.text = data['summary_time'] ?? '09:00';
        _selectedTimezone = data['timezone'] ?? 'America/New_York';

        // IMAP Configuration
        _imapEnabled = data['imap_enabled'] ?? false;
        _imapHostController.text = data['imap_host'] ?? '';
        _imapPortController.text = data['imap_port']?.toString() ?? '993';
        _imapUsernameController.text = data['imap_username'] ?? '';
        _imapPasswordController.text = data['imap_password'] ?? '';
        _mailboxNameController.text = data['mailbox_name'] ?? 'INBOX';
        _checkInterval = data['check_interval'] ?? 5;
        _imapSsl = data['imap_ssl'] ?? true;

        // Auto-reply
        _autoReplyEnabled = data['auto_reply_enabled'] ?? false;
        _replySignatureController.text = data['reply_signature'] ?? '';

        _isLoading = false;
      });
      
      loggingService.info('Email settings loaded successfully', screen: 'EmailSettingsScreen');
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'EmailSettingsScreen');
      
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load email settings: ${e.toString()}';
      });
    }
  }

  Future<void> _saveEmailSettings() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isSaving = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Save Email Settings', screen: 'EmailSettingsScreen', data: {
        'dailySummaryEnabled': _dailySummaryEnabled,
        'imapEnabled': _imapEnabled,
        'autoReplyEnabled': _autoReplyEnabled,
      });
      
      await apiService.post(AppConstants.emailSettingsEndpoint, data: {
        // SMTP Configuration
        'smtp_host': _smtpHostController.text.trim(),
        'smtp_port': int.tryParse(_smtpPortController.text) ?? 587,
        'smtp_username': _smtpUsernameController.text.trim(),
        'smtp_password': _smtpPasswordController.text.trim(),
        'from_email': _fromEmailController.text.trim(),
        'recipient_email': _recipientEmailController.text.trim(),
        'smtp_tls': _smtpTls,
        'smtp_ssl': _smtpSsl,

        // Daily Summary
        'daily_summary_enabled': _dailySummaryEnabled,
        'summary_time': _summaryTimeController.text.trim(),
        'timezone': _selectedTimezone,

        // IMAP Configuration
        'imap_enabled': _imapEnabled,
        'imap_host': _imapHostController.text.trim(),
        'imap_port': int.tryParse(_imapPortController.text) ?? 993,
        'imap_username': _imapUsernameController.text.trim(),
        'imap_password': _imapPasswordController.text.trim(),
        'mailbox_name': _mailboxNameController.text.trim(),
        'check_interval': _checkInterval,
        'imap_ssl': _imapSsl,

        // Auto-reply
        'auto_reply_enabled': _autoReplyEnabled,
        'reply_signature': _replySignatureController.text.trim(),
      });

      loggingService.info('Email settings saved successfully', screen: 'EmailSettingsScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Email settings saved successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'EmailSettingsScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save email settings: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } finally {
      setState(() {
        _isSaving = false;
      });
    }
  }

  Future<void> _testEmail() async {
    setState(() {
      _isSaving = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Test Email', screen: 'EmailSettingsScreen');
      
      await apiService.post(AppConstants.testEmailEndpoint, data: {});

      loggingService.info('Test email sent successfully', screen: 'EmailSettingsScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Test email sent successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'EmailSettingsScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to send test email: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } finally {
      setState(() {
        _isSaving = false;
      });
    }
  }

  Future<void> _generateSignature() async {
    setState(() {
      _isGeneratingSignature = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      
      loggingService.logUserAction('Generate Email Signature', screen: 'EmailSettingsScreen');
      
      final response = await apiService.post(AppConstants.generateSignatureEndpoint, data: {});
      
      setState(() {
        _replySignatureController.text = response.data['signature'] ?? '';
      });

      loggingService.info('Signature generated successfully', screen: 'EmailSettingsScreen');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Signature generated successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e, stackTrace) {
      final loggingService = Provider.of<LoggingService>(context, listen: false);
      loggingService.logException(e, stackTrace, screen: 'EmailSettingsScreen');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to generate signature: ${e.toString()}'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } finally {
      setState(() {
        _isGeneratingSignature = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Email Settings'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadEmailSettings,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _isLoading
          ? const LoadingIndicator(message: 'Loading email settings...')
          : _errorMessage != null
              ? _buildErrorState()
              : Form(
                  key: _formKey,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(AppTheme.spacingM),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildSmtpConfig(),
                        const SizedBox(height: AppTheme.spacingL),
                        _buildDailySummaryConfig(),
                        const SizedBox(height: AppTheme.spacingL),
                        _buildImapConfig(),
                        const SizedBox(height: AppTheme.spacingL),
                        _buildAutoReplyConfig(),
                        const SizedBox(height: AppTheme.spacingL),
                        _buildActionButtons(),
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
              'Error Loading Email Settings',
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
              onPressed: _loadEmailSettings,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSmtpConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'SMTP Configuration',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _smtpHostController,
                    decoration: const InputDecoration(
                      labelText: 'SMTP Host',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.dns),
                    ),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Please enter SMTP host';
                      }
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: AppTheme.spacingM),
                SizedBox(
                  width: 100,
                  child: TextFormField(
                    controller: _smtpPortController,
                    decoration: const InputDecoration(
                      labelText: 'Port',
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.number,
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Required';
                      }
                      final port = int.tryParse(value);
                      if (port == null || port < 1 || port > 65535) {
                        return 'Invalid port';
                      }
                      return null;
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _smtpUsernameController,
                    decoration: const InputDecoration(
                      labelText: 'Username',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.person),
                    ),
                  ),
                ),
                const SizedBox(width: AppTheme.spacingM),
                Expanded(
                  child: TextFormField(
                    controller: _smtpPasswordController,
                    decoration: const InputDecoration(
                      labelText: 'Password',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.lock),
                    ),
                    obscureText: true,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _fromEmailController,
                    decoration: const InputDecoration(
                      labelText: 'From Email',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.email),
                    ),
                    keyboardType: TextInputType.emailAddress,
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Please enter from email';
                      }
                      if (!RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$').hasMatch(value)) {
                        return 'Please enter a valid email';
                      }
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: AppTheme.spacingM),
                Expanded(
                  child: TextFormField(
                    controller: _recipientEmailController,
                    decoration: const InputDecoration(
                      labelText: 'Recipient Email',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.email_outlined),
                    ),
                    keyboardType: TextInputType.emailAddress,
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Please enter recipient email';
                      }
                      if (!RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$').hasMatch(value)) {
                        return 'Please enter a valid email';
                      }
                      return null;
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppTheme.spacingM),
            Row(
              children: [
                Expanded(
                  child: CheckboxListTile(
                    title: const Text('Use TLS'),
                    value: _smtpTls,
                    onChanged: (value) {
                      setState(() {
                        _smtpTls = value ?? false;
                      });
                    },
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
                Expanded(
                  child: CheckboxListTile(
                    title: const Text('Use SSL'),
                    value: _smtpSsl,
                    onChanged: (value) {
                      setState(() {
                        _smtpSsl = value ?? false;
                      });
                    },
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDailySummaryConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Daily Summary',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            SwitchListTile(
              title: const Text('Enable Daily Summary'),
              value: _dailySummaryEnabled,
              onChanged: (value) {
                setState(() {
                  _dailySummaryEnabled = value;
                });
              },
            ),
            if (_dailySummaryEnabled) ...[
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _summaryTimeController,
                      decoration: const InputDecoration(
                        labelText: 'Summary Time',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.access_time),
                        hintText: 'HH:MM',
                      ),
                      validator: (value) {
                        if (_dailySummaryEnabled && (value == null || value.trim().isEmpty)) {
                          return 'Please enter summary time';
                        }
                        if (value != null && value.isNotEmpty) {
                          if (!RegExp(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$').hasMatch(value)) {
                            return 'Please enter time in HH:MM format';
                          }
                        }
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingM),
                  Expanded(
                    child: DropdownButtonFormField<String>(
                      value: _selectedTimezone,
                      decoration: const InputDecoration(
                        labelText: 'Timezone',
                        border: OutlineInputBorder(),
                      ),
                      items: AppConstants.timezones.map((timezone) => DropdownMenuItem<String>(
                        value: timezone,
                        child: Text(AppConstants.timezoneDisplayNames[timezone] ?? timezone),
                      )).toList(),
                      onChanged: (value) {
                        setState(() {
                          _selectedTimezone = value!;
                        });
                      },
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildImapConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'IMAP Configuration',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            SwitchListTile(
              title: const Text('Enable IMAP'),
              value: _imapEnabled,
              onChanged: (value) {
                setState(() {
                  _imapEnabled = value;
                });
              },
            ),
            if (_imapEnabled) ...[
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _imapHostController,
                      decoration: const InputDecoration(
                        labelText: 'IMAP Host',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.dns),
                      ),
                      validator: (value) {
                        if (_imapEnabled && (value == null || value.trim().isEmpty)) {
                          return 'Please enter IMAP host';
                        }
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingM),
                  SizedBox(
                    width: 100,
                    child: TextFormField(
                      controller: _imapPortController,
                      decoration: const InputDecoration(
                        labelText: 'Port',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                      validator: (value) {
                        if (_imapEnabled && (value == null || value.trim().isEmpty)) {
                          return 'Required';
                        }
                        if (value != null && value.isNotEmpty) {
                          final port = int.tryParse(value);
                          if (port == null || port < 1 || port > 65535) {
                            return 'Invalid port';
                          }
                        }
                        return null;
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _imapUsernameController,
                      decoration: const InputDecoration(
                        labelText: 'Username',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.person),
                      ),
                      validator: (value) {
                        if (_imapEnabled && (value == null || value.trim().isEmpty)) {
                          return 'Please enter username';
                        }
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingM),
                  Expanded(
                    child: TextFormField(
                      controller: _imapPasswordController,
                      decoration: const InputDecoration(
                        labelText: 'Password',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.lock),
                      ),
                      obscureText: true,
                      validator: (value) {
                        if (_imapEnabled && (value == null || value.trim().isEmpty)) {
                          return 'Please enter password';
                        }
                        return null;
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppTheme.spacingM),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _mailboxNameController,
                      decoration: const InputDecoration(
                        labelText: 'Mailbox Name',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.folder),
                        hintText: 'INBOX',
                      ),
                    ),
                  ),
                  const SizedBox(width: AppTheme.spacingM),
                  Expanded(
                    child: DropdownButtonFormField<int>(
                      value: _checkInterval,
                      decoration: const InputDecoration(
                        labelText: 'Check Interval (minutes)',
                        border: OutlineInputBorder(),
                      ),
                      items: [1, 5, 10, 15, 30, 60].map((interval) => DropdownMenuItem<int>(
                        value: interval,
                        child: Text('$interval minutes'),
                      )).toList(),
                      onChanged: (value) {
                        setState(() {
                          _checkInterval = value!;
                        });
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppTheme.spacingM),
              CheckboxListTile(
                title: const Text('Use SSL'),
                value: _imapSsl,
                onChanged: (value) {
                  setState(() {
                    _imapSsl = value ?? false;
                  });
                },
                contentPadding: EdgeInsets.zero,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildAutoReplyConfig() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Auto-Reply Settings',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            SwitchListTile(
              title: const Text('Enable Auto-Reply'),
              value: _autoReplyEnabled,
              onChanged: (value) {
                setState(() {
                  _autoReplyEnabled = value;
                });
              },
            ),
            if (_autoReplyEnabled) ...[
              const SizedBox(height: AppTheme.spacingM),
              TextFormField(
                controller: _replySignatureController,
                decoration: const InputDecoration(
                  labelText: 'Reply Signature',
                  border: OutlineInputBorder(),
                  hintText: 'Enter your auto-reply message...',
                ),
                maxLines: 5,
                validator: (value) {
                  if (_autoReplyEnabled && (value == null || value.trim().isEmpty)) {
                    return 'Please enter reply signature';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppTheme.spacingM),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _isGeneratingSignature ? null : _generateSignature,
                  icon: _isGeneratingSignature
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.auto_awesome),
                  label: const Text('Generate Signature with AI'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildActionButtons() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppTheme.spacingM),
        child: Column(
          children: [
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isSaving ? null : _testEmail,
                icon: _isSaving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send),
                label: const Text('Send Test Email'),
              ),
            ),
            const SizedBox(height: AppTheme.spacingM),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isSaving ? null : _saveEmailSettings,
                icon: _isSaving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save),
                label: const Text('Save Email Settings'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
