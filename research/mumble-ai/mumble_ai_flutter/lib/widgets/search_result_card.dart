import 'package:flutter/material.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class SearchResultCard extends StatelessWidget {
  final String type; // 'conversation' or 'entity'
  final String content;
  final String? userName;
  final String? timestamp;
  final double? relevanceScore;
  final String? entityType;
  final String? contextInfo;
  final VoidCallback? onTap;

  const SearchResultCard({
    Key? key,
    required this.type,
    required this.content,
    this.userName,
    this.timestamp,
    this.relevanceScore,
    this.entityType,
    this.contextInfo,
    this.onTap,
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
              if (contextInfo != null) ...[
                const SizedBox(height: AppTheme.spacingS),
                _buildContextInfo(context),
              ],
              if (userName != null || timestamp != null) ...[
                const SizedBox(height: AppTheme.spacingS),
                _buildFooter(context),
              ],
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
            color: _getTypeColor().withOpacity(0.1),
            borderRadius: BorderRadius.circular(AppTheme.radiusS),
            border: Border.all(
              color: _getTypeColor().withOpacity(0.3),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                _getTypeIcon(),
                size: 14,
                color: _getTypeColor(),
              ),
              const SizedBox(width: AppTheme.spacingXS),
              Text(
                type.toUpperCase(),
                style: TextStyle(
                  color: _getTypeColor(),
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
        if (entityType != null) ...[
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
              AppConstants.entityTypeDisplayNames[entityType!] ?? entityType!,
              style: const TextStyle(
                color: AppTheme.primaryColor,
                fontWeight: FontWeight.w600,
                fontSize: 12,
              ),
            ),
          ),
        ],
        const Spacer(),
        if (relevanceScore != null) ...[
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppTheme.spacingS,
              vertical: AppTheme.spacingXS,
            ),
            decoration: BoxDecoration(
              color: _getRelevanceColor().withOpacity(0.1),
              borderRadius: BorderRadius.circular(AppTheme.radiusS),
            ),
            child: Text(
              '${(relevanceScore! * 100).toStringAsFixed(0)}%',
              style: TextStyle(
                color: _getRelevanceColor(),
                fontWeight: FontWeight.w600,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildContent(BuildContext context) {
    return Text(
      content,
      style: AppTheme.messageBubbleStyle,
      maxLines: 3,
      overflow: TextOverflow.ellipsis,
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
              contextInfo!,
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
        if (userName != null) ...[
          Icon(
            Icons.person,
            size: 14,
            color: AppTheme.textSecondary,
          ),
          const SizedBox(width: AppTheme.spacingXS),
          Text(
            userName!,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
        if (userName != null && timestamp != null) ...[
          const SizedBox(width: AppTheme.spacingM),
          Icon(
            Icons.circle,
            size: 4,
            color: AppTheme.textTertiary,
          ),
          const SizedBox(width: AppTheme.spacingM),
        ],
        if (timestamp != null) ...[
          Icon(
            Icons.access_time,
            size: 14,
            color: AppTheme.textSecondary,
          ),
          const SizedBox(width: AppTheme.spacingXS),
          Text(
            _formatTimestamp(timestamp!),
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ],
    );
  }

  Color _getTypeColor() {
    switch (type.toLowerCase()) {
      case 'conversation':
        return AppTheme.infoColor;
      case 'entity':
        return AppTheme.warningColor;
      default:
        return AppTheme.primaryColor;
    }
  }

  IconData _getTypeIcon() {
    switch (type.toLowerCase()) {
      case 'conversation':
        return Icons.chat;
      case 'entity':
        return Icons.label;
      default:
        return Icons.help;
    }
  }

  Color _getRelevanceColor() {
    if (relevanceScore == null) return AppTheme.textSecondary;
    if (relevanceScore! >= 0.8) return AppTheme.successColor;
    if (relevanceScore! >= 0.6) return AppTheme.warningColor;
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
