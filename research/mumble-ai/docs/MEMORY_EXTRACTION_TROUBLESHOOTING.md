# Memory Extraction Troubleshooting

## Overview

The memory extraction system uses Ollama to analyze conversations and automatically extract important information (schedules, facts, tasks, preferences) to save as persistent memories. This document covers common issues and solutions.

## Common Issues

### JSON Parsing Errors

**Symptom:**
```
ERROR - Error extracting memory: Expecting value: line X column Y (char Z)
```

**Cause:**
The LLM (Ollama) is returning malformed JSON that cannot be parsed. This happens when:
- The model adds explanatory text before/after the JSON
- The JSON has syntax errors (missing commas, quotes, etc.)
- The model doesn't follow the JSON format strictly
- The model response is truncated

**Solution:**
The bot now includes **multiple fallback strategies** to handle malformed JSON:

1. **Direct parsing**: Tries to parse the response as-is
2. **Regex extraction**: Extracts JSON array from surrounding text
3. **Cleaning**: Removes markdown code blocks, trailing commas, extra text
4. **Validation**: Validates and repairs memory objects

**What Was Fixed:**
- ✅ Added 4 different JSON parsing strategies
- ✅ Better error messages with response preview
- ✅ Validation of memory structure before saving
- ✅ Auto-correction of invalid categories and importance values
- ✅ Graceful fallback when parsing fails (doesn't crash)
- ✅ Improved prompt for stricter JSON compliance
- ✅ Lower temperature (0.2) for more consistent output
- ✅ Response length limit to prevent truncation

### No Memories Being Extracted

**Symptom:**
```
DEBUG - No important memories found in conversation with [username]
```

**Cause:**
This is normal behavior when conversations don't contain information worth remembering (e.g., simple greetings, casual chat).

**Expected Behavior:**
- Small talk: No memories extracted ✓
- Important dates/events: Should extract as 'schedule'
- Personal preferences: Should extract as 'preference'
- Tasks/reminders: Should extract as 'task'
- Personal facts: Should extract as 'fact'

**Check if it's working:**
```sql
-- View recent memory extractions
SELECT user_name, category, content, importance, extracted_at
FROM persistent_memories
ORDER BY extracted_at DESC
LIMIT 10;
```

### Memory Extraction Timeouts

**Symptom:**
```
ERROR - Network error during memory extraction: timeout
```

**Cause:**
- Ollama is slow or unresponsive
- Model is too large for your hardware
- Network issues between bot and Ollama

**Solutions:**

1. **Check Ollama status:**
```bash
curl http://localhost:11434/api/tags
```

2. **Switch to a faster model:**
```sql
UPDATE bot_config 
SET value = 'llama3.2:1b'  -- Smaller, faster model
WHERE key = 'ollama_model';
```

3. **Increase timeout** (in `bot.py`):
```python
timeout=60  # Increase from 30 to 60 seconds
```

### Invalid Categories or Importance Values

**Symptom:**
```
WARNING - Invalid category 'appointment', defaulting to 'other'
WARNING - Importance 15 out of range, clamping to 1-10
```

**Cause:**
The LLM used an invalid category name or importance value outside the valid range.

**Solution:**
The bot now automatically corrects these:
- Invalid categories → default to 'other'
- Importance < 1 → set to 1
- Importance > 10 → set to 10

Valid categories: `schedule`, `fact`, `task`, `preference`, `other`

### Duplicate Memories

**Symptom:**
The same information is saved multiple times.

**Cause:**
The extraction runs after each conversation exchange, and similar information might be mentioned repeatedly.

**Solutions:**

1. **Check for duplicates:**
```sql
SELECT user_name, category, content, COUNT(*) as count
FROM persistent_memories
WHERE active = TRUE
GROUP BY user_name, category, content
HAVING COUNT(*) > 1;
```

2. **Remove duplicates manually:**
```sql
-- Keep only the most recent duplicate
DELETE FROM persistent_memories
WHERE id IN (
    SELECT id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY user_name, category, content 
                   ORDER BY extracted_at DESC
               ) as rn
        FROM persistent_memories
        WHERE active = TRUE
    ) t
    WHERE t.rn > 1
);
```

3. **Deactivate instead of delete:**
```sql
UPDATE persistent_memories
SET active = FALSE
WHERE id IN (
    -- same subquery as above
);
```

## Debugging Memory Extraction

### Enable Debug Logging

The bot logs the first 200 characters of the LLM response for debugging:

```
DEBUG - Memory extraction raw response: [{"category": "schedule", "content": "...
```

To see full responses, temporarily modify the log level:

```python
# In bot.py, add after line 973:
logger.info(f"Full memory extraction response: {result}")
```

### Test Memory Extraction Manually

You can test the extraction by checking the database after a conversation:

```sql
-- See what memories were extracted from your recent conversation
SELECT 
    pm.user_name,
    pm.category,
    pm.content,
    pm.importance,
    pm.extracted_at,
    cs.session_id
FROM persistent_memories pm
JOIN conversation_sessions cs ON pm.session_id = cs.session_id
WHERE pm.user_name = 'YourUsername'
  AND pm.extracted_at > NOW() - INTERVAL '1 hour'
ORDER BY pm.extracted_at DESC;
```

### Monitor Extraction Success Rate

```sql
-- Count conversations vs memories extracted
SELECT 
    DATE(timestamp) as date,
    COUNT(DISTINCT session_id) as conversations,
    (SELECT COUNT(*) FROM persistent_memories 
     WHERE DATE(extracted_at) = DATE(ch.timestamp)) as memories_extracted
FROM conversation_history ch
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

## Configuration

### Adjust Extraction Sensitivity

You can tune how aggressively the system extracts memories by modifying the prompt in `bot.py` (line 933):

**More aggressive** (extracts more):
```python
extraction_prompt = f"""Extract ALL information from this conversation that could be useful later...
```

**More conservative** (extracts less):
```python
extraction_prompt = f"""Extract only CRITICAL information like appointments, important deadlines, and major life events...
```

### Model Selection

Different models have different JSON compliance:

**Best for JSON:**
- `qwen2.5-coder:7b` - Very good at structured output
- `llama3.2:3b` - Good balance of speed and accuracy
- `gemma2:2b` - Fast, decent JSON compliance

**Avoid for JSON:**
- Very small models (<1B parameters) - inconsistent formatting
- Chat-optimized models - tend to add explanatory text

### Temperature Settings

Lower temperature = more consistent JSON:
- `0.1` - Most consistent (may be too rigid)
- `0.2` - **Recommended** (good balance)
- `0.3` - More creative (less consistent)
- `0.5+` - Too variable for JSON extraction

## Best Practices

1. **Monitor extraction errors** in logs:
```bash
docker-compose logs -f mumble-bot | grep "Error extracting memory"
```

2. **Periodically review extracted memories:**
```sql
SELECT category, COUNT(*) 
FROM persistent_memories 
WHERE active = TRUE 
GROUP BY category;
```

3. **Clean up old/irrelevant memories:**
```sql
-- Mark old memories as inactive
UPDATE persistent_memories
SET active = FALSE
WHERE extracted_at < NOW() - INTERVAL '90 days'
  AND category IN ('task', 'reminder');
```

4. **Test with different models** to find the best balance of speed and accuracy for your hardware.

## Error Reference

| Error | Severity | Action Required |
|-------|----------|----------------|
| `Expecting value: line X column Y` | Low | None - automatically handled |
| `Network error during memory extraction` | Medium | Check Ollama status |
| `Could not parse JSON from memory extraction` | Low | Check model and prompt |
| `Invalid category '...'` | Low | None - auto-corrected |
| `Importance ... out of range` | Low | None - auto-corrected |

## When to Disable Memory Extraction

If memory extraction is causing issues, you can disable it by commenting out the extraction call in `bot.py`:

```python
# Around line 557 and 625, comment out:
# threading.Thread(
#     target=self.extract_and_save_memory,
#     args=(message, response_text, sender_name, session_id),
#     daemon=True
# ).start()
```

**Note:** This disables automatic memory extraction but doesn't affect:
- ✅ Conversation history (still saved)
- ✅ Session management (still works)
- ✅ Short-term memory (still available)
- ✅ Existing persistent memories (still used)

## Getting Help

If you're still experiencing issues:

1. **Check the logs:**
```bash
docker-compose logs -f mumble-bot | grep -A 5 "Error extracting memory"
```

2. **Verify Ollama is working:**
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:latest",
  "prompt": "Return only: []",
  "stream": false
}'
```

3. **Check database connectivity:**
```bash
docker-compose exec postgres psql -U mumbleai -d mumble_ai -c "SELECT COUNT(*) FROM persistent_memories;"
```

4. **Review recent changes:**
```sql
SELECT key, value, updated_at 
FROM bot_config 
WHERE key IN ('ollama_model', 'ollama_url')
ORDER BY updated_at DESC;
```

