# Session Management System

## Overview

The Mumble AI Bot uses a robust session management system to ensure the AI assistant remains available even when sessions are closed or become idle. This document explains how session lifecycle management works and how to configure it.

## Session States

Sessions can be in one of three states:

1. **active** - Currently in use, user is actively interacting
2. **idle** - Inactive but can be reactivated if user returns soon
3. **closed** - Finished, will not be reactivated

## Session Lifecycle

### 1. Session Creation

When a user first interacts with the bot (voice or text), a new session is created:

```python
session_id = f"{user_name}_{uuid.uuid4().hex[:8]}_{int(time.time())}"
```

The session is stored in the database with:
- `user_name`: Username of the person interacting
- `session_id`: Unique identifier for this conversation
- `started_at`: When the session was created
- `last_activity`: Last time the user interacted
- `state`: Current state ('active', 'idle', or 'closed')
- `message_count`: Number of messages in this session

### 2. Active Session Management

While a user is interacting:
- Each message updates `last_activity` timestamp
- The session state remains 'active'
- Conversation history is linked to the `session_id`
- The bot maintains context across messages

### 3. Session Idle Detection

The bot periodically checks for idle sessions:

```python
def close_idle_sessions(self):
    """Close sessions that have been idle for too long"""
    timeout_minutes = int(self.get_config('session_timeout_minutes', '30'))
    # Mark sessions as 'idle' if no activity for timeout_minutes
```

**Default timeout**: 30 minutes (configurable via `session_timeout_minutes`)

When a session becomes idle:
- Database state changes from 'active' to 'idle'
- Session is removed from in-memory cache
- Conversation history is preserved in the database
- The bot continues running normally

### 4. Session Reactivation

When a user returns after their session became idle, the bot can reactivate the session:

```python
def _get_recent_idle_session(self, user_name: str) -> Optional[str]:
    """Get the most recent idle session for a user if within reactivation window"""
    reactivation_window_minutes = int(self.get_config('session_reactivation_minutes', '10'))
    # Find idle sessions within the reactivation window
```

**Default reactivation window**: 10 minutes (configurable via `session_reactivation_minutes`)

**Reactivation behavior**:
- If the user returns within 10 minutes: The idle session is reactivated, conversation context is preserved
- If the user returns after 10 minutes: A new session is created

This ensures:
- Short interruptions don't lose context
- Long absences start fresh conversations
- The bot is always available regardless of session state

### 5. Session Verification

Before reusing a cached session, the bot verifies it's still valid:

```python
def _verify_session_active(self, session_id: str) -> bool:
    """Verify that a session is still active in the database"""
    # Check if session exists and is in 'active' state
```

This prevents using stale or invalid sessions.

## Configuration

All session management settings are stored in the database `bot_config` table and can be adjusted via the web control panel:

| Configuration Key | Default | Description |
|-------------------|---------|-------------|
| `session_timeout_minutes` | 30 | How long before an active session becomes idle |
| `session_reactivation_minutes` | 10 | How long an idle session can be reactivated |

### Adjusting Settings

**Via Web Control Panel:**
1. Navigate to the web control panel (port 5002)
2. Go to Configuration settings
3. Update the desired values
4. Changes take effect immediately

**Via Database:**
```sql
UPDATE bot_config 
SET value = '60' 
WHERE key = 'session_timeout_minutes';

UPDATE bot_config 
SET value = '15' 
WHERE key = 'session_reactivation_minutes';
```

## Bot Availability Guarantee

The bot remains available at all times:

1. **Bot Process**: Runs continuously in a Docker container
2. **Session Independence**: Session lifecycle doesn't affect bot availability
3. **Automatic Session Creation**: New sessions are created automatically when needed
4. **Database Persistence**: All session data is preserved in PostgreSQL
5. **Health Monitoring**: Background health checks ensure bot is responsive

### What Happens When a Session Closes?

1. Session state changes to 'idle' in database
2. Session removed from in-memory cache (`user_sessions` dict)
3. **Bot continues running** - no interruption to service
4. When user returns:
   - Recent idle sessions can be reactivated (preserves context)
   - New sessions created if needed
   - Bot responds immediately

### Example Timeline

```
Time    Event                           Session State    Bot Status
------  ------------------------------  ---------------  -----------
10:00   User starts conversation        Active           Running
10:05   User sends message              Active           Running
10:35   30 min timeout reached          Idle             Running
10:40   User returns (within 10 min)    Active (reused)  Running
11:10   30 min timeout reached          Idle             Running
11:30   User returns (after 10 min)     New session      Running
```

## Database Schema

### conversation_sessions Table

```sql
CREATE TABLE conversation_sessions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    state VARCHAR(20) DEFAULT 'active' CHECK (state IN ('active', 'idle', 'closed')),
    message_count INTEGER DEFAULT 0,
    UNIQUE(user_name, session_id)
);
```

### Indexes
- `idx_session_user`: Fast lookup by username
- `idx_session_activity`: Fast sorting by last activity

## Troubleshooting

### Bot Not Responding After Session Timeout

**Symptoms**: User tries to interact but gets no response

**Causes**:
- Bot container crashed (not session-related)
- Database connection issue
- Service health check failing

**Check**:
```bash
# Check bot container status
docker-compose ps mumble-bot

# Check bot logs
docker-compose logs -f mumble-bot

# Check database connection
docker-compose logs -f postgres
```

### Sessions Not Being Reactivated

**Symptoms**: New session created even though user returned quickly

**Causes**:
- Reactivation window too short
- Database latency
- Clock synchronization issues

**Solutions**:
1. Increase `session_reactivation_minutes`:
   ```sql
   UPDATE bot_config SET value = '15' WHERE key = 'session_reactivation_minutes';
   ```

2. Check database performance:
   ```sql
   SELECT session_id, user_name, last_activity, state
   FROM conversation_sessions
   WHERE user_name = 'YourUsername'
   ORDER BY last_activity DESC
   LIMIT 5;
   ```

### Too Many Idle Sessions

**Symptoms**: Database has many idle sessions

**Causes**:
- Normal operation - idle sessions accumulate over time
- Session cleanup not running

**Solutions**:
1. Sessions are automatically marked as idle - this is expected
2. To clean up old idle sessions manually:
   ```sql
   UPDATE conversation_sessions
   SET state = 'closed'
   WHERE state = 'idle'
     AND last_activity < NOW() - INTERVAL '7 days';
   ```

## Performance Considerations

### Memory Usage

- Active sessions: Stored in `user_sessions` dictionary (in-memory)
- Idle/closed sessions: Only in database, minimal memory impact
- Session data: Lightweight, only session ID and metadata

### Database Load

- Session queries are indexed for fast lookup
- Connection pooling prevents database overload
- Background cleanup runs every 5 minutes
- Minimal overhead per session check

### Scalability

The system is designed to handle:
- Hundreds of concurrent active sessions
- Thousands of idle sessions in database
- High-frequency user interactions
- Long-running bot instances (weeks/months)

## Best Practices

1. **Monitor Session States**: Periodically check session distribution
   ```sql
   SELECT state, COUNT(*) 
   FROM conversation_sessions 
   GROUP BY state;
   ```

2. **Archive Old Sessions**: Clean up sessions older than a threshold
   ```sql
   DELETE FROM conversation_sessions
   WHERE state = 'closed'
     AND last_activity < NOW() - INTERVAL '30 days';
   ```

3. **Tune Timeouts**: Adjust based on your usage patterns
   - Short sessions (chat-like): 15-30 minutes
   - Long sessions (extended conversation): 60+ minutes

4. **Monitor Bot Health**: Use health check endpoint
   ```bash
   curl http://localhost:8080/health
   ```

## Migration

If you're upgrading from an older version without session reactivation:

1. Apply the database migration:
   ```bash
   docker-compose exec postgres psql -U mumbleai -d mumble_ai < sql/migrate-database.sql
   ```

2. Restart the bot container:
   ```bash
   docker-compose restart mumble-bot
   ```

3. Verify configuration:
   ```sql
   SELECT key, value 
   FROM bot_config 
   WHERE key LIKE 'session_%';
   ```

Expected output:
```
session_timeout_minutes        | 30
session_reactivation_minutes   | 10
```

## Summary

The enhanced session management system ensures:
- ✅ Bot is always available regardless of session state
- ✅ Sessions automatically transition between active/idle/closed
- ✅ Recent idle sessions can be reactivated to preserve context
- ✅ New sessions created seamlessly when needed
- ✅ All session data persisted in database
- ✅ Configurable timeouts for different use cases
- ✅ Minimal performance impact
- ✅ Robust error handling and verification

