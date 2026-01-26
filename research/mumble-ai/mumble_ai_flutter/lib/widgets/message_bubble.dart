import 'package:flutter/material.dart';
import '../utils/theme.dart';

class MessageBubble extends StatelessWidget {
  final String message;
  final bool isUser;
  final String? timestamp;
  final VoidCallback? onCopy;

  const MessageBubble({
    Key? key,
    required this.message,
    required this.isUser,
    this.timestamp,
    this.onCopy,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(
        vertical: AppTheme.spacingXS,
        horizontal: AppTheme.spacingM,
      ),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
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
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              padding: const EdgeInsets.symmetric(
                horizontal: AppTheme.spacingM,
                vertical: AppTheme.spacingS,
              ),
              decoration: BoxDecoration(
                color: isUser ? AppTheme.primaryColor : AppTheme.backgroundColor,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(AppTheme.radiusL),
                  topRight: const Radius.circular(AppTheme.radiusL),
                  bottomLeft: Radius.circular(isUser ? AppTheme.radiusL : AppTheme.radiusS),
                  bottomRight: Radius.circular(isUser ? AppTheme.radiusS : AppTheme.radiusL),
                ),
                border: !isUser ? Border.all(color: AppTheme.borderColor) : null,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    message,
                    style: AppTheme.messageBubbleStyle.copyWith(
                      color: isUser ? Colors.white : AppTheme.textPrimary,
                    ),
                  ),
                  if (timestamp != null) ...[
                    const SizedBox(height: AppTheme.spacingXS),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          timestamp!,
                          style: AppTheme.timestampStyle.copyWith(
                            color: isUser 
                                ? Colors.white.withOpacity(0.7) 
                                : AppTheme.textTertiary,
                          ),
                        ),
                        if (onCopy != null)
                          GestureDetector(
                            onTap: onCopy,
                            child: Icon(
                              Icons.copy,
                              size: 14,
                              color: isUser 
                                  ? Colors.white.withOpacity(0.7) 
                                  : AppTheme.textTertiary,
                            ),
                          ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: AppTheme.spacingS),
            const CircleAvatar(
              radius: 16,
              backgroundColor: AppTheme.textSecondary,
              child: Icon(
                Icons.person,
                size: 16,
                color: Colors.white,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
