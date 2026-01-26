# Email Summary Retry Feature

## Overview
The email summary service now includes automatic retry logic with exponential backoff when Ollama API calls fail, plus a manual retry feature accessible from the web control panel.

## Features

### 1. Automatic Retry with Exponential Backoff
When the email-summary-service calls Ollama to generate summaries or email replies, it will automatically retry up to 3 times if the request fails or times out.

**Retry Logic:**
- **Attempt 1**: Initial request (120s timeout)
- **Wait 2 seconds** → **Attempt 2**: Retry (120s timeout)
- **Wait 4 seconds** → **Attempt 3**: Final retry (120s timeout)

If all 3 attempts fail, the error is logged to the database for manual retry.

### 2. Failed Email Logging
When Ollama fails after all retries, the failure is logged to the `email_logs` table with:
- **Status**: `error`
- **Error Message**: Clear description including "Ollama API failed after 3 retry attempts"
- **Full Context**: From address, to address, subject, body preview

### 3. Manual Retry from Web Interface
Failed emails can be manually retried from the web control panel.

#### How to Use:
1. **Access Web Control Panel**: Navigate to `http://localhost:5002`
2. **View Email Logs**: Scroll to the "Email Activity Logs" section
3. **Filter Failed Emails**: Use the status filter dropdown and select "Error"
4. **Retry**: Click the **🔄 Retry Sending** button on any failed email
5. **Monitor Result**: The UI will show status updates and auto-refresh after success

#### Retry Behavior:
- **Summary with Ollama failure**: Triggers a fresh summary generation with new Ollama attempts
- **Reply with Ollama failure**: Queued for automatic retry on next email check cycle
- **SMTP failure**: Immediately resends the existing email content

## Technical Details

### Port Configuration
- **Email Summary Service API**: Port **5006**
  - Health check: `http://localhost:5006/health`
  - Manual trigger: `POST http://localhost:5006/api/send-summary`

### API Endpoints

#### Web Control Panel
```http
POST /api/email/retry/<log_id>
```
Triggers a retry for the specified failed email log entry.

**Response:**
```json
{
  "success": true,
  "message": "Summary regeneration triggered. Check email logs for results."
}
```

#### Email Summary Service
```http
POST /api/send-summary
```
Manually triggers a daily summary generation and send.

**Response:**
```json
{
  "success": true,
  "message": "Summary generation started"
}
```

```http
GET /health
```
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "email-summary"
}
```

## Error Messages

### Ollama Timeout
```
Ollama API failed after 3 retry attempts - summary generation timed out. Click retry to attempt again.
```

### SMTP Failure
```
Failed to send email via SMTP
```

## Configuration

### Environment Variables
No additional configuration required. The retry logic is built-in with these defaults:
- **Max Retries**: 3
- **Timeout per attempt**: 120 seconds
- **Backoff**: Exponential (2^attempt seconds)

### Database Schema
The `email_logs` table tracks all email activity including failures:

```sql
CREATE TABLE email_logs (
    id SERIAL PRIMARY KEY,
    direction VARCHAR(10) NOT NULL,
    email_type VARCHAR(20) NOT NULL,
    from_email VARCHAR(255) NOT NULL,
    to_email VARCHAR(255) NOT NULL,
    subject TEXT,
    body_preview TEXT,
    full_body TEXT,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    mapped_user VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Logging

### Service Logs
Monitor retry attempts in the email-summary-service logs:

```bash
docker logs email-summary-service -f
```

**Example output:**
```
2025-10-10 16:00:00 - INFO - Ollama API call attempt 1/3
2025-10-10 16:02:00 - WARNING - Ollama request timed out on attempt 1/3: Timeout after 120s
2025-10-10 16:02:00 - INFO - Waiting 2s before retry...
2025-10-10 16:02:02 - INFO - Ollama API call attempt 2/3
2025-10-10 16:04:02 - WARNING - Ollama request timed out on attempt 2/3: Timeout after 120s
2025-10-10 16:04:02 - INFO - Waiting 4s before retry...
2025-10-10 16:04:06 - INFO - Ollama API call attempt 3/3
2025-10-10 16:06:06 - ERROR - All 3 Ollama API attempts failed. Last error: Timeout after 120s
```

## Troubleshooting

### Issue: Retry button doesn't work
**Check:**
1. Verify email-summary-service is running: `docker ps | grep email-summary`
2. Check service logs: `docker logs email-summary-service --tail 50`
3. Test API endpoint: `curl http://localhost:5006/health`

### Issue: All retries still fail
**Possible causes:**
1. **Ollama not running**: Start Ollama service
2. **Ollama overloaded**: Check Ollama logs and system resources
3. **Model not available**: Verify the configured model exists: `curl http://localhost:11434/api/tags`
4. **Network issues**: Check Docker network connectivity

### Issue: Summary generates but email doesn't send
**Check:**
1. SMTP settings in web control panel
2. Test email functionality: Click "Send Test Email" button
3. Check firewall rules for SMTP ports (587, 465, 25)

## Files Modified

### Core Changes
- `email-summary-service/app.py` - Added retry logic and Flask API
- `email-summary-service/requirements.txt` - Added Flask dependency
- `web-control-panel/app.py` - Added retry endpoint
- `web-control-panel/templates/index.html` - Added retry button UI
- `docker-compose.yml` - Exposed port 5006

### Documentation
- `docs/EMAIL_RETRY_FEATURE.md` - This file
- `README.md` - Updated service ports

## Related Documentation
- [Email Summaries Guide](EMAIL_SUMMARIES_GUIDE.md)
- [Web Control Panel](../README.md#web-control-panel)
- [API Documentation](API.md)
- [Troubleshooting](TROUBLESHOOTING.md)

