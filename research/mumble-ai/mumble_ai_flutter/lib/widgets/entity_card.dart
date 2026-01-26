import 'package:flutter/material.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';
import '../models/entity.dart';

class EntityCard extends StatelessWidget {
  final Entity entity;
  final VoidCallback? onTap;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;

  const EntityCard({
    Key? key,
    required this.entity,
    this.onTap,
    this.onEdit,
    this.onDelete,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: AppTheme.spacingS),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppTheme.radiusL),
        child: Padding(
          padding: const EdgeInsets.all(AppTheme.spacingM),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(context),
              const SizedBox(height: AppTheme.spacingS),
              _buildContent(context),
              if (entity.contextInfo != null) ...[
                const SizedBox(height: AppTheme.spacingS),
                _buildContextInfo(context),
              ],
              const SizedBox(height: AppTheme.spacingS),
              _buildFooter(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppTheme.spacingS,
            vertical: AppTheme.spacingXS,
          ),
          decoration: BoxDecoration(
            color: _getEntityTypeColor().withOpacity(0.1),
            borderRadius: BorderRadius.circular(AppTheme.radiusS),
            border: Border.all(
              color: _getEntityTypeColor().withOpacity(0.3),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                _getEntityTypeIcon(),
                size: 14,
                color: _getEntityTypeColor(),
              ),
              const SizedBox(width: AppTheme.spacingXS),
              Text(
                entity.entityTypeDisplay,
                style: TextStyle(
                  color: _getEntityTypeColor(),
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: AppTheme.spacingS),
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppTheme.spacingS,
            vertical: AppTheme.spacingXS,
          ),
          decoration: BoxDecoration(
            color: _getConfidenceColor().withOpacity(0.1),
            borderRadius: BorderRadius.circular(AppTheme.radiusS),
            border: Border.all(
              color: _getConfidenceColor().withOpacity(0.3),
            ),
          ),
          child: Text(
            entity.confidenceLevel,
            style: TextStyle(
              color: _getConfidenceColor(),
              fontWeight: FontWeight.w600,
              fontSize: 12,
            ),
          ),
        ),
        const Spacer(),
        PopupMenuButton<String>(
          onSelected: (value) {
            if (value == 'edit') {
              onEdit?.call();
            } else if (value == 'delete') {
              onDelete?.call();
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
    );
  }

  Widget _buildContent(BuildContext context) {
    return Text(
      entity.entityText,
      style: AppTheme.messageBubbleStyle.copyWith(
        fontWeight: FontWeight.w600,
      ),
    );
  }

  Widget _buildContextInfo(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spacingS),
      decoration: BoxDecoration(
        color: AppTheme.backgroundColor,
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
        border: Border.all(color: AppTheme.borderColor),
      ),
      child: Row(
        children: [
          Icon(
            Icons.info_outline,
            size: 16,
            color: AppTheme.textSecondary,
          ),
          const SizedBox(width: AppTheme.spacingS),
          Expanded(
            child: Text(
              entity.contextInfo!,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooter(BuildContext context) {
    return Row(
      children: [
        Icon(
          Icons.person,
          size: 14,
          color: AppTheme.textSecondary,
        ),
        const SizedBox(width: AppTheme.spacingXS),
        Text(
          entity.userName,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: AppTheme.textSecondary,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(width: AppTheme.spacingM),
        Icon(
          Icons.circle,
          size: 4,
          color: AppTheme.textTertiary,
        ),
        const SizedBox(width: AppTheme.spacingM),
        Icon(
          Icons.percent,
          size: 14,
          color: AppTheme.textSecondary,
        ),
        const SizedBox(width: AppTheme.spacingXS),
        Text(
          '${(entity.confidence * 100).toStringAsFixed(0)}%',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: AppTheme.textSecondary,
          ),
        ),
        if (entity.createdAt != null) ...[
          const SizedBox(width: AppTheme.spacingM),
          Icon(
            Icons.circle,
            size: 4,
            color: AppTheme.textTertiary,
          ),
          const SizedBox(width: AppTheme.spacingM),
          Icon(
            Icons.access_time,
            size: 14,
            color: AppTheme.textSecondary,
          ),
          const SizedBox(width: AppTheme.spacingXS),
          Text(
            _formatTimestamp(entity.createdAt!),
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ],
    );
  }

  Color _getEntityTypeColor() {
    switch (entity.entityType) {
      case 'PERSON':
        return AppTheme.successColor;
      case 'PLACE':
        return AppTheme.infoColor;
      case 'ORGANIZATION':
        return AppTheme.warningColor;
      case 'DATE':
      case 'TIME':
        return AppTheme.primaryColor;
      case 'EVENT':
        return AppTheme.errorColor;
      default:
        return AppTheme.textSecondary;
    }
  }

  IconData _getEntityTypeIcon() {
    switch (entity.entityType) {
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

  Color _getConfidenceColor() {
    if (entity.confidence >= 0.9) return AppTheme.successColor;
    if (entity.confidence >= 0.7) return AppTheme.warningColor;
    return AppTheme.errorColor;
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
