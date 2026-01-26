# Email Summary System

## Overview

The Mumble AI bot now includes a **Daily Email Summary** feature that automatically generates and sends comprehensive summaries of conversation history via email. The system uses Ollama to create intelligent, well-formatted summaries and delivers them at your chosen time each day.

## Features

✅ **Automated daily summaries** of all conversations
✅ **AI-generated content** using Ollama for intelligent summarization
✅ **Configurable schedule** - send emails at any time (default: 10pm EST)
✅ **Beautiful HTML emails** with responsive design
✅ **Full SMTP support** including TLS/SSL authentication
✅ **Web-based configuration** through the control panel
✅ **Test email functionality** to verify settings
✅ **Timezone-aware scheduling** with multiple timezone options

## Quick Start

1. **Access the Web Control Panel**
   Navigate to `http://localhost:5002`

2. **Scroll to the "📧 Email Summary Settings" section**

3. **Configure SMTP Settings**:
   - **SMTP Host**: Your mail server (e.g., `mail.example.com` or `localhost`)
   - **SMTP Port**: Usually `25` (plain), `587` (TLS), or `465` (SSL)
   - **SMTP Username/Password**: Credentials if required by your mail server
   - **TLS/SSL**: Check the appropriate box for your server's security requirements

4. **Configure Email Settings**:
   - **From Email**: The sender address (e.g., `mumble-ai@example.com`)
   - **Recipient Email**: Where to send the summaries
   - **Summary Time**: When to send daily (24-hour format, default `22:00`)
   - **Timezone**: Your preferred timezone (default EST)
   - **Enable Daily Summaries**: Check to activate automatic sending

5. **Test Your Configuration**:
   - Click "Send Test Email" to verify settings work correctly
   - Check your inbox for the test message

6. **Save Settings**:
   - Click "Save Email Settings" to store your configuration

## How It Works

### Scheduling
The email summary service runs continuously and checks every 60 seconds whether it's time to send the daily summary. When the current time matches your configured "Summary Time", the system:

1. **Retrieves conversation history** from the last 24 hours
2. **Generates a summary** using Ollama AI
3. **Formats the email** with HTML styling
4. **Sends via SMTP** to your configured recipient
5. **Records the timestamp** to prevent duplicate sends

### Summary Content

The AI-generated summary includes:

- **Overview**: Total message count, unique users, main topics discussed
- **Key Conversations**: Highlights of important or interesting exchanges
- **Persistent Information**: Schedules, tasks, facts, and preferences mentioned
- **Statistics**: Activity metrics and conversation distribution

### Email Format

Emails are sent in both **plain text** and **HTML** formats for maximum compatibility:

- **Plain text**: Simple, readable version for basic email clients
- **HTML**: Beautiful, styled version with:
  - Gradient header with Mumble AI branding
  - Color-coded sections
  - Responsive design for mobile devices
  - Professional formatting

## Configuration Options

### SMTP Settings

| Setting | Description | Example |
|---------|-------------|---------|
| **SMTP Host** | Mail server hostname or IP | `mail.example.com`, `10.0.0.50` |
| **SMTP Port** | Mail server port | `25`, `587`, `465` |
| **SMTP Username** | Authentication username (optional) | `mumble-bot` |
| **SMTP Password** | Authentication password (optional) | `secret123` |
| **Use TLS** | Enable STARTTLS encryption | ☑ for port 587 |
| **Use SSL** | Enable SSL/TLS encryption | ☑ for port 465 |

### Email Settings

| Setting | Description | Example |
|---------|-------------|---------|
| **From Email** | Sender address | `mumble-ai@example.com` |
| **Recipient Email** | Where to send summaries | `admin@example.com` |
| **Summary Time** | When to send (24-hour format) | `22:00` (10pm) |
| **Timezone** | Local timezone for scheduling | `America/New_York` |
| **Enable Daily Summaries** | Activate automatic sending | ☑ |

### Supported Timezones

- `America/New_York` - Eastern Time (EST/EDT)
- `America/Chicago` - Central Time (CST/CDT)
- `America/Denver` - Mountain Time (MST/MDT)
- `America/Los_Angeles` - Pacific Time (PST/PDT)
- `UTC` - Coordinated Universal Time

## Using Your Mail Relay

If you have an existing mail relay (like in a single-node stack), configure it as follows:

### Example: Local Mail Relay on Port 25

```
SMTP Host: localhost (or IP of your mail relay)
SMTP Port: 25
SMTP Username: (leave empty if relay doesn't require auth)
SMTP Password: (leave empty if relay doesn't require auth)
Use TLS: ☐ (unchecked for local relay)
Use SSL: ☐ (unchecked for local relay)
```

### Example: External SMTP with Authentication

```
SMTP Host: smtp.gmail.com
SMTP Port: 587
SMTP Username: your-email@gmail.com
SMTP Password: your-app-password
Use TLS: ☑ (checked)
Use SSL: ☐ (unchecked)
```

## API Endpoints

The email summary system provides the following REST API endpoints:

### GET `/api/email/settings`
Retrieve current email configuration

**Response:**
```json
{
  "smtp_host": "localhost",
  "smtp_port": 25,
  "smtp_username": "",
  "smtp_use_tls": false,
  "smtp_use_ssl": false,
  "from_email": "mumble-ai@localhost",
  "recipient_email": "admin@example.com",
  "daily_summary_enabled": true,
  "summary_time": "22:00:00",
  "timezone": "America/New_York",
  "last_sent": "2025-10-04T22:00:15.123456"
}
```

### POST `/api/email/settings`
Update email configuration

**Request Body:**
```json
{
  "smtp_host": "mail.example.com",
  "smtp_port": 587,
  "smtp_username": "bot@example.com",
  "smtp_password": "secret123",
  "smtp_use_tls": true,
  "from_email": "mumble-ai@example.com",
  "recipient_email": "admin@example.com",
  "daily_summary_enabled": true,
  "summary_time": "22:00:00",
  "timezone": "America/New_York"
}
```

### POST `/api/email/test`
Send a test email using current settings

**Response:**
```json
{
  "success": true,
  "message": "Test email sent successfully"
}
```

## Database Schema

### email_settings Table

```sql
CREATE TABLE email_settings (
    id SERIAL PRIMARY KEY,
    smtp_host VARCHAR(255) NOT NULL DEFAULT 'localhost',
    smtp_port INTEGER NOT NULL DEFAULT 25,
    smtp_username VARCHAR(255),
    smtp_password VARCHAR(255),
    smtp_use_tls BOOLEAN DEFAULT FALSE,
    smtp_use_ssl BOOLEAN DEFAULT FALSE,
    from_email VARCHAR(255) NOT NULL DEFAULT 'mumble-ai@localhost',
    recipient_email VARCHAR(255),
    daily_summary_enabled BOOLEAN DEFAULT FALSE,
    summary_time TIME DEFAULT '22:00:00',
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    last_sent TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Troubleshooting

### Email Not Sending

1. **Check email summary service logs**:
   ```bash
   docker-compose logs -f email-summary-service
   ```

2. **Verify SMTP settings**:
   - Test with "Send Test Email" button
   - Check SMTP host is reachable
   - Verify port is correct (25, 587, or 465)
   - Ensure TLS/SSL settings match your server

3. **Check daily summaries are enabled**:
   - Open web control panel
   - Verify "Enable Daily Summaries" is checked
   - Confirm recipient email is set

4. **Verify scheduling**:
   - Check current time matches summary time
   - Verify timezone setting is correct
   - View last_sent timestamp in database

### Test Email Fails

**Common Issues:**

- **Connection refused**: SMTP host or port incorrect
- **Authentication failed**: Wrong username/password
- **TLS/SSL error**: Wrong security setting for the port
- **Recipient rejected**: Mail server doesn't accept the recipient address

**Solutions:**

1. Verify SMTP server is running:
   ```bash
   telnet smtp-host 25
   ```

2. Check firewall rules allow outbound SMTP

3. Test with a simple SMTP client like `swaks` or `sendmail`

4. Review email-summary-service logs for detailed error messages

### Summary Content Is Empty

1. **Check conversation history**:
   ```bash
   docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT COUNT(*) FROM conversation_history WHERE timestamp >= NOW() - INTERVAL '24 hours';"
   ```

2. **Verify Ollama is running**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. **Check Ollama model is available**:
   - Verify model name in database matches available models
   - Ensure model is downloaded: `ollama pull llama3.2`

### Emails Sending Multiple Times

- Check `last_sent` timestamp in database
- Verify only one instance of email-summary-service is running
- Review service logs for duplicate send attempts

## Manual Email Sending

To manually trigger a summary email (for testing):

```bash
# Get current email settings
curl http://localhost:5002/api/email/settings

# Send test email
curl -X POST http://localhost:5002/api/email/test
```

## Migration Guide

If upgrading from an older Mumble AI installation:

```bash
# Apply the email settings migration
docker exec -i mumble-ai-postgres psql -U mumbleai mumble_ai < migrate-email.sql

# Rebuild services
docker-compose build email-summary-service web-control-panel

# Restart all services
docker-compose up -d
```

## Service Architecture

```
email-summary-service (Docker container)
├── Connects to PostgreSQL for configuration and conversation history
├── Connects to Ollama for AI-powered summarization
├── Sends emails via configured SMTP relay
└── Runs continuously, checking schedule every 60 seconds

web-control-panel (Docker container)
├── Provides UI for email configuration
├── API endpoints for settings management
└── Test email functionality
```

## Environment Variables

The email summary service supports the following environment variables:

```bash
# Database connection
DB_HOST=postgres
DB_PORT=5432
DB_NAME=mumble_ai
DB_USER=mumbleai
DB_PASSWORD=mumbleai123

# Ollama connection
OLLAMA_URL=http://host.docker.internal:11434

# Service configuration
CHECK_INTERVAL_SECONDS=60  # How often to check if it's time to send
```

## Security Considerations

⚠️ **Important Security Notes:**

1. **SMTP Passwords**: Stored in plain text in the database. For production:
   - Use environment variables for sensitive credentials
   - Consider Docker secrets for password management
   - Restrict database access

2. **Mail Relay**: If using an open relay:
   - Ensure it's only accessible from trusted networks
   - Configure SPF/DKIM records to prevent spoofing
   - Consider rate limiting

3. **Email Content**: Summaries include conversation history:
   - Ensure recipient email is secure
   - Consider encryption for sensitive conversations
   - Review privacy policies before enabling

## Performance Notes

- **Email generation**: Uses Ollama, takes 5-30 seconds depending on conversation volume
- **Database queries**: Optimized with indexes on timestamp columns
- **Memory usage**: ~50MB for email-summary-service container
- **CPU usage**: Minimal except during summary generation
- **Network**: One SMTP connection per email sent

## Attachment Processing

### Overview

The email bot can now read and analyze attachments sent via email! When you email the bot with an attachment and ask questions about it, the bot will use AI vision models (for images) or text extraction (for PDFs and Word documents) to understand the content and provide helpful responses.

### Supported Attachment Types

| Type | Extensions | Processing Method | Max Size |
|------|-----------|-------------------|----------|
| **Images** | JPG, JPEG, PNG, GIF, WEBP | Vision AI (Moondream) | 10MB |
| **PDF Documents** | PDF | Text extraction (PyPDF2) | 10MB |
| **Word Documents** | DOCX, DOC | Text extraction (python-docx) | 10MB |

### How to Use

1. **Send an email** to your configured IMAP address with one or more attachments
2. **Ask questions** about the attachments in the email body
3. **Receive an AI-generated reply** that answers your questions based on the attachment analysis

**Example:**
```
Subject: What's in this image?

Email Body:
Hey bot, can you tell me what's in the attached screenshot? 
Also, what do you think about the document I attached?

Attachments:
- screenshot.png (2.5 MB)
- report.pdf (1.8 MB)
```

The bot will:
- Analyze the image using the vision model (Moondream by default)
- Extract and read the text from the PDF
- Generate a personalized response answering your questions about both attachments

### Vision Model Configuration

The bot uses **Moondream** by default for image analysis. Moondream is fast, efficient, and runs well on most hardware.

**To change the vision model:**

1. Navigate to the Web Control Panel at `http://localhost:5002`
2. Scroll to the **"👁️ Vision Model (Email Attachments)"** section
3. Select a different model from the dropdown:
   - `moondream:latest` (recommended - fast and efficient)
   - `llava:latest` (more detailed analysis, slower)
   - `bakllava:latest` (specialized for certain tasks)
   - `llama3.2-vision:latest` (if available)
4. Click **"Save Vision Model"**

**Available models** depend on what you have downloaded in Ollama. To download a vision model:

```bash
ollama pull moondream
ollama pull llava
ollama pull bakllava
```

### Features

✅ **Multiple attachments** - Process multiple files in a single email
✅ **Individual analysis** - Each attachment is analyzed separately 
✅ **Combined response** - The bot provides context-aware answers referencing specific attachments
✅ **Full logging** - All attachment activity is logged in the web control panel
✅ **Automatic cleanup** - Temporary files are deleted after processing
✅ **Size limits** - Attachments over 10MB are automatically rejected with a warning
✅ **Persona maintained** - The bot maintains its configured persona when discussing attachments

### Web Control Panel Display

Email logs in the web control panel now show:

- 📎 **Attachment count badge** on emails with attachments
- **Filename and type** for each attachment (🖼️ images, 📄 PDFs, 📝 docs)
- **File size** in KB
- **Analysis preview** (first 200 characters of the vision analysis or extracted text)

Navigate to the **"📬 Email Activity Logs"** section to view attachment details.

### How It Works

**For Images:**
1. Image is resized to max 800px width (if larger)
2. Converted to base64 encoding
3. Sent to Ollama vision model with a description prompt
4. AI analyzes the image and describes what it sees
5. Analysis is included in the bot's reply

**For PDFs:**
1. Text is extracted from all pages using PyPDF2
2. Pages are concatenated with page markers
3. Text is limited to first 5000 characters if too long
4. Extracted text is included in the bot's context
5. Bot can answer questions about the document content

**For Word Documents:**
1. All paragraphs are extracted using python-docx
2. Text is joined together
3. Limited to first 5000 characters if too long
4. Extracted text is used to answer questions

### Temporary Storage

Attachments are saved temporarily during processing:

- **Location**: `/tmp/mumble-attachments/{timestamp}/`
- **Lifetime**: Deleted immediately after email reply is sent
- **Security**: Each email gets its own timestamped directory

### Error Handling

The system handles various error scenarios gracefully:

- **Unsupported file types**: Logged with warning, mentioned in reply
- **Corrupt files**: Error logged, processing continues for other attachments
- **Large files (>10MB)**: Skipped with warning in logs
- **Vision model unavailable**: Falls back to "Unable to analyze image" message
- **Ollama timeout**: Uses retry logic (3 attempts with exponential backoff)

### Limitations

- Maximum **10MB per attachment**
- Only the file types listed above are supported
- Vision analysis quality depends on the chosen model
- PDF text extraction may not work with scanned/image-based PDFs
- Processing time increases with file size and number of attachments

### Troubleshooting

**Vision model not working:**

1. Check Ollama is running: `ollama list`
2. Download the vision model: `ollama pull moondream`
3. Verify in web control panel that the correct model is selected
4. Check email-summary-service logs: `docker-compose logs -f email-summary-service`

**Attachments not being processed:**

1. Check attachment size (must be under 10MB)
2. Verify file type is supported
3. Check email-summary-service logs for errors
4. Ensure IMAP receiving and auto-reply are enabled

**Poor image analysis:**

1. Try a different vision model (llava may provide more detail)
2. Ensure image is clear and not too large
3. Check that Ollama has enough resources

## Future Enhancements

Possible improvements for future versions:

- 📊 **Weekly digest** mode with aggregated statistics
- 📧 **Multiple recipients** support
- 🎨 **Customizable email templates**
- 📅 **Per-user summaries** sent to individual email addresses
- 🔍 **Keyword filtering** to include only relevant conversations
- 🔐 **Encrypted emails** for sensitive content
- 📱 **SMS summaries** via Twilio integration
- 🔍 **OCR support** for scanned PDFs and images with text

## Support

For issues, feature requests, or questions:

1. Check the logs: `docker-compose logs -f email-summary-service`
2. Review this guide's troubleshooting section
3. Open an issue on the GitHub repository
4. Check database state: `docker exec mumble-ai-postgres psql -U mumbleai mumble_ai -c "SELECT * FROM email_settings;"`

---

## Summary

The Email Summary System provides a powerful way to stay informed about conversations happening in your Mumble server, even when you're not online. With AI-powered summarization and flexible scheduling, you'll receive comprehensive, well-formatted updates exactly when you want them.

To get started, simply configure your SMTP settings in the web control panel at `http://localhost:5002` and enable daily summaries!
