# Email Bot Analysis and Enhancement Plan

**Date**: October 10, 2025
**Purpose**: Analysis of current email bot implementation and plan for making it smarter with thread-aware conversations and action result reporting

---

## Current Implementation Issues

### 1. No Email Thread Tracking
- Bot doesn't maintain conversation context per email subject/thread
- Each email is treated as an independent conversation
- No way to reference previous messages in the same thread
- Uses `in_reply_to` and `references` headers but doesn't persist thread relationships

### 2. No Action Result Reporting
**Current Flow** (lines 3162-3173 in email-summary-service/app.py):
```python
# Send reply first
success = self.send_reply_email(...)

if success:
    # THEN run actions in background daemon threads (fire-and-forget)
    threading.Thread(
        target=self.extract_and_save_memory,
        args=(body, reply_text, mapped_user or sender_email, None),
        daemon=True
    ).start()

    threading.Thread(
        target=self.extract_and_manage_schedule,
        args=(body, reply_text, mapped_user or sender_email),
        daemon=True
    ).start()
```

**Problems**:
- Reply is sent BEFORE actions are executed
- Actions run in daemon threads (fire-and-forget)
- No way to track success/failure
- User never knows if memory was saved or calendar event was created
- If action fails, user has no idea

### 3. Context Is Global, Not Thread-Specific
**Current Context** (lines 2401-2431 in generate_ai_reply):
- Retrieves ALL memories for the user (global)
- Retrieves ALL upcoming schedule events (global)
- Has access to attachments analysis
- **MISSING**: Previous messages in this email thread
- **MISSING**: What actions were previously attempted in this thread

### 4. Conversation History Is Not Tracked
- `generate_ai_reply()` doesn't maintain conversation history per thread
- Each reply is generated fresh without context of previous emails in thread
- User has to re-explain context in every email

---

## User Requirements

1. **Thread-Aware Context**: Conversations should be tracked by email subject (thread)
2. **Access to Memories & Calendar**: Bot should still have access to global memories and calendar
3. **Action Result Reporting**: Bot must report whether it successfully added memories/calendar events
4. **Failure Explanations**: If actions fail, bot must explain what happened and why in the email

---

## Proposed Solution

### Database Schema Changes

#### 1. Create `email_threads` Table
Track conversation threads by subject line:

```sql
CREATE TABLE email_threads (
    id SERIAL PRIMARY KEY,
    subject TEXT NOT NULL,
    normalized_subject TEXT NOT NULL,  -- Subject with Re:/Fwd: removed
    user_email VARCHAR(255) NOT NULL,
    mapped_user VARCHAR(255),  -- User name from mapping
    first_message_id VARCHAR(500),  -- Message-ID of first email
    last_message_id VARCHAR(500),  -- Message-ID of last email
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(normalized_subject, user_email)
);

CREATE INDEX idx_email_threads_user ON email_threads(user_email);
CREATE INDEX idx_email_threads_normalized ON email_threads(normalized_subject);
```

#### 2. Add `thread_id` to `email_logs` Table
Link email logs to threads:

```sql
ALTER TABLE email_logs ADD COLUMN thread_id INTEGER REFERENCES email_threads(id);
CREATE INDEX idx_email_logs_thread ON email_logs(thread_id);
```

#### 3. Create `email_actions` Table
Track memory/calendar actions per thread:

```sql
CREATE TABLE email_actions (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER REFERENCES email_threads(id),
    email_log_id INTEGER REFERENCES email_logs(id),
    action_type VARCHAR(20) NOT NULL CHECK (action_type IN ('memory', 'schedule')),
    action VARCHAR(20) NOT NULL CHECK (action IN ('add', 'update', 'delete', 'nothing')),
    intent TEXT,  -- What the AI intended to do
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'skipped')),
    details JSONB,  -- Action details (memory content, event details, etc.)
    error_message TEXT,  -- If failed, why?
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_actions_thread ON email_actions(thread_id);
CREATE INDEX idx_email_actions_status ON email_actions(status);
```

#### 4. Create `email_thread_messages` Table
Store conversation history per thread (separate from Mumble conversations):

```sql
CREATE TABLE email_thread_messages (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER REFERENCES email_threads(id),
    email_log_id INTEGER REFERENCES email_logs(id),
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    message_content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_thread_messages_thread ON email_thread_messages(thread_id);
CREATE INDEX idx_thread_messages_timestamp ON email_thread_messages(timestamp);
```

---

### Code Changes

#### 1. Thread Management Functions

**Add to EmailSummaryService class**:

```python
def normalize_subject(self, subject: str) -> str:
    """Remove Re:, Fwd:, etc. from subject to identify thread"""
    import re
    # Remove Re:, RE:, re:, Fwd:, FW:, etc.
    normalized = re.sub(r'^(Re|RE|re|Fwd|FW|fw):\s*', '', subject, flags=re.IGNORECASE)
    normalized = normalized.strip()
    return normalized

def get_or_create_thread(self, subject: str, user_email: str,
                         mapped_user: str, message_id: str) -> int:
    """Get existing thread or create new one based on subject"""
    normalized_subject = self.normalize_subject(subject)

    conn = self.get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Try to find existing thread
            cursor.execute("""
                SELECT id, message_count
                FROM email_threads
                WHERE normalized_subject = %s AND user_email = %s
            """, (normalized_subject, user_email))

            row = cursor.fetchone()
            if row:
                thread_id, msg_count = row
                # Update thread
                cursor.execute("""
                    UPDATE email_threads
                    SET last_message_id = %s,
                        message_count = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (message_id, msg_count + 1, thread_id))
                conn.commit()
                return thread_id
            else:
                # Create new thread
                cursor.execute("""
                    INSERT INTO email_threads
                    (subject, normalized_subject, user_email, mapped_user,
                     first_message_id, last_message_id, message_count)
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                    RETURNING id
                """, (subject, normalized_subject, user_email, mapped_user,
                      message_id, message_id))
                thread_id = cursor.fetchone()[0]
                conn.commit()
                return thread_id
    finally:
        conn.close()

def get_thread_history(self, thread_id: int, limit: int = 10) -> List[Dict]:
    """Get recent conversation history for this email thread"""
    conn = self.get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role, message_content, timestamp
                FROM email_thread_messages
                WHERE thread_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (thread_id, limit))

            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'role': row[0],
                    'message': row[1],
                    'timestamp': row[2]
                })
            return list(reversed(messages))  # Return chronological order
    finally:
        conn.close()

def save_thread_message(self, thread_id: int, email_log_id: int,
                        role: str, message: str):
    """Save message to thread history"""
    conn = self.get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO email_thread_messages
                (thread_id, email_log_id, role, message_content)
                VALUES (%s, %s, %s, %s)
            """, (thread_id, email_log_id, role, message))
            conn.commit()
    finally:
        conn.close()

def get_thread_actions(self, thread_id: int, limit: int = 5) -> List[Dict]:
    """Get recent actions from this thread"""
    conn = self.get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT action_type, action, intent, status, details,
                       error_message, executed_at
                FROM email_actions
                WHERE thread_id = %s
                ORDER BY executed_at DESC
                LIMIT %s
            """, (thread_id, limit))

            actions = []
            for row in cursor.fetchall():
                actions.append({
                    'action_type': row[0],
                    'action': row[1],
                    'intent': row[2],
                    'status': row[3],
                    'details': row[4],
                    'error_message': row[5],
                    'executed_at': row[6]
                })
            return list(reversed(actions))
    finally:
        conn.close()

def log_action(self, thread_id: int, email_log_id: int, action_type: str,
               action: str, intent: str, status: str, details: dict = None,
               error_message: str = None):
    """Log an action attempt (memory or schedule)"""
    conn = self.get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO email_actions
                (thread_id, email_log_id, action_type, action, intent,
                 status, details, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (thread_id, email_log_id, action_type, action, intent,
                  status, json.dumps(details) if details else None, error_message))
            conn.commit()
    finally:
        conn.close()
```

#### 2. Modified Email Reply Generation

Update `generate_ai_reply()` to accept thread context:

```python
def generate_ai_reply(self, sender: str, subject: str, body: str, settings: Dict,
                      thread_id: int = None, attachments_analysis: List[Dict] = None) -> str:
    """Generate AI reply with thread-aware context and action history"""

    # ... existing code for user mapping, persona, memories, schedule ...

    # NEW: Get thread conversation history
    thread_context = ""
    if thread_id:
        thread_history = self.get_thread_history(thread_id, limit=10)
        if thread_history:
            thread_context = "\n📧 PREVIOUS MESSAGES IN THIS EMAIL THREAD:\n"
            for msg in thread_history:
                role_label = "You" if msg['role'] == 'assistant' else mapped_user or sender
                thread_context += f"{role_label}: {msg['message']}\n"
            thread_context += "\n"

    # NEW: Get recent actions from this thread
    actions_context = ""
    if thread_id:
        recent_actions = self.get_thread_actions(thread_id, limit=5)
        if recent_actions:
            actions_context = "\n🔧 RECENT ACTIONS IN THIS THREAD:\n"
            for action in recent_actions:
                status_icon = "✅" if action['status'] == 'success' else "❌"
                actions_context += f"{status_icon} {action['action_type'].upper()} - {action['action']}: {action['intent']}\n"
                if action['status'] == 'failed':
                    actions_context += f"   Error: {action['error_message']}\n"
            actions_context += "\n"

    # Create prompt with thread context
    reply_prompt = f"""You are {bot_persona}.

You are responding to an email thread from {mapped_user if mapped_user else sender}.

{thread_context}{actions_context}IMPORTANT CONTEXT ABOUT THE EMAIL SENDER ({mapped_user if mapped_user else sender}):
{memory_context}{schedule_context}
CURRENT EMAIL:
From: {sender}
Subject: {subject}

Message:
{body}
{attachments_context}
---

CRITICAL INSTRUCTIONS:
- This is part of an ongoing email thread - reference previous messages if relevant
- If there were recent actions (memories saved, calendar events created), acknowledge them
- If actions failed, explain what happened and why
- The schedule and memories belong to THE EMAIL SENDER, not you
- Use "you" or "your" when referring to their schedule, NEVER "I" or "my"

... rest of prompt ...
"""

    # ... rest of function ...
```

#### 3. Synchronous Action Execution

Replace daemon threads with synchronous execution and result tracking:

```python
def process_actions_and_reply(self, sender_email: str, subject: str, body: str,
                               settings: Dict, thread_id: int, email_log_id: int,
                               mapped_user: str, attachments_analysis: List[Dict] = None):
    """
    Process actions FIRST, then generate reply with results included
    Returns: (reply_text, actions_performed)
    """
    actions_performed = []

    # STEP 1: Extract and execute memory actions
    try:
        memory_results = self.extract_and_save_memory_sync(
            body, mapped_user or sender_email, None
        )
        for result in memory_results:
            self.log_action(
                thread_id=thread_id,
                email_log_id=email_log_id,
                action_type='memory',
                action='add',
                intent=result.get('content', ''),
                status='success' if result.get('saved') else 'failed',
                details=result,
                error_message=result.get('error')
            )
            actions_performed.append(result)
    except Exception as e:
        logger.error(f"Memory extraction failed: {e}")
        self.log_action(
            thread_id=thread_id,
            email_log_id=email_log_id,
            action_type='memory',
            action='add',
            intent='Extract memories from email',
            status='failed',
            error_message=str(e)
        )

    # STEP 2: Extract and execute schedule actions
    try:
        schedule_results = self.extract_and_manage_schedule_sync(
            body, mapped_user or sender_email
        )
        for result in schedule_results:
            self.log_action(
                thread_id=thread_id,
                email_log_id=email_log_id,
                action_type='schedule',
                action=result.get('action', 'add'),
                intent=result.get('title', ''),
                status='success' if result.get('saved') else 'failed',
                details=result,
                error_message=result.get('error')
            )
            actions_performed.append(result)
    except Exception as e:
        logger.error(f"Schedule extraction failed: {e}")
        self.log_action(
            thread_id=thread_id,
            email_log_id=email_log_id,
            action_type='schedule',
            action='add',
            intent='Extract schedule from email',
            status='failed',
            error_message=str(e)
        )

    # STEP 3: Generate reply with thread context (includes action results)
    reply_text = self.generate_ai_reply(
        sender_email, subject, body, settings,
        thread_id=thread_id,
        attachments_analysis=attachments_analysis
    )

    return reply_text, actions_performed
```

#### 4. Updated Email Processing Flow

Modify `check_and_reply_to_emails()`:

```python
# ... after parsing email ...

# Get or create thread
thread_id = self.get_or_create_thread(
    subject=subject,
    user_email=sender_email,
    mapped_user=mapped_user,
    message_id=message_id
)

# Log received email with thread_id
email_log_id = self.log_email(
    direction='received',
    email_type='other',
    from_email=sender_email,
    to_email=settings['imap_username'],
    subject=subject,
    body=body,
    status='success',
    mapped_user=mapped_user,
    thread_id=thread_id,  # NEW
    attachments_count=len(attachments_analysis),
    attachments_metadata=attachments_metadata
)

# Save user message to thread history
self.save_thread_message(
    thread_id=thread_id,
    email_log_id=email_log_id,
    role='user',
    message=body
)

# Process actions and generate reply
reply_text, actions = self.process_actions_and_reply(
    sender_email, subject, body, settings,
    thread_id, email_log_id, mapped_user,
    attachments_analysis
)

if reply_text:
    # Send reply
    success = self.send_reply_email(...)

    if success:
        # Save assistant message to thread history
        self.save_thread_message(
            thread_id=thread_id,
            email_log_id=reply_email_log_id,
            role='assistant',
            message=reply_text
        )
```

---

## Summary of Changes

### Database
- ✅ New `email_threads` table for thread tracking
- ✅ New `email_thread_messages` table for conversation history per thread
- ✅ New `email_actions` table for tracking action results
- ✅ Add `thread_id` column to `email_logs`

### Code
- ✅ Thread management functions (create, retrieve, track)
- ✅ Thread conversation history functions
- ✅ Action logging functions
- ✅ Modified `generate_ai_reply()` to include thread context and action history
- ✅ Synchronous action execution (replace daemon threads)
- ✅ Updated email processing flow to track threads

### Benefits
- ✅ Bot maintains conversation context per email thread
- ✅ Bot can reference previous messages in the thread
- ✅ Bot reports success/failure of memory and calendar actions
- ✅ Bot explains why actions failed (with error messages)
- ✅ Still has access to global memories and calendar
- ✅ Thread-specific context doesn't pollute other conversations

---

## Implementation Order

1. Create database migration SQL script
2. Add thread management functions
3. Add action logging functions
4. Modify `extract_and_save_memory` to return results (not daemon thread)
5. Modify `extract_and_manage_schedule` to return results (not daemon thread)
6. Create `process_actions_and_reply()` function
7. Update `generate_ai_reply()` to accept thread context
8. Modify `check_and_reply_to_emails()` to use new flow
9. Test with real emails
10. Update documentation

---

## Testing Scenarios

1. **New thread**: Send email, verify bot creates thread, executes actions, reports results
2. **Existing thread**: Reply to existing thread, verify bot remembers context
3. **Action success**: Bot adds memory, reports "I've saved that to memory"
4. **Action failure**: Simulate DB error, verify bot reports "I couldn't save that because..."
5. **Multiple actions**: Email with both memory and calendar, verify both tracked
6. **Thread isolation**: Two different subjects, verify contexts don't mix
