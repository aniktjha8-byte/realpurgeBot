# Bunny CDN Cache Purge Bot

A Telegram bot that automates Bunny CDN cache purging from uploaded text files containing multiple accounts and URLs.

## Features

- 📤 **Smart File Upload**: Automatic encoding detection (UTF-8, Latin-1, etc.)
- 🔍 **Validation**: URL format, API key, and file structure validation
- 🔄 **Batch Processing**: Purge multiple URLs across multiple accounts in one go
- ⚡ **Concurrent Requests**: 15 simultaneous requests for 3-5x faster processing
- 🔁 **Auto-Resume**: Interrupted purges automatically save progress
- 🔄 **Smart Retry**: Exponential backoff for failed URLs (up to 3 retries)
- 📊 **Real-time Progress**: Live updates with speed and ETA
- 🛡️ **Error Recovery**: Comprehensive error handling with state persistence
- 📄 **Detailed Reports**: Success/failure breakdown for each account
- 🔒 **Single User Access**: Restrict bot to one authorized Telegram account

## Prerequisites

- Python 3.8 or higher
- A Telegram Bot Token (get it from [@BotFather](https://t.me/botfather))
- Bunny CDN API keys for your pull zones

## Deployment Options

### Option 1: Deploy on Replit (Recommended for 24/7 uptime)

1. **Fork this repository to Replit**:
   - Go to [Replit](https://replit.com)
   - Click "Create Repl" → "Import from GitHub"
   - Paste this repository URL

2. **Configure Secrets**:
   - In Replit, go to the "Secrets" tab (lock icon in left sidebar)
   - Add a new secret:
     - Key: `TELEGRAM_BOT_TOKEN`
     - Value: Your bot token from [@BotFather](https://t.me/botfather)

3. **Run Setup** (optional):
   ```bash
   bash setup.sh
   ```

4. **Start the Bot**:
   - Click the "Run" button
   - The bot will automatically start with keep-alive enabled

**Replit Features:**
- ✅ Automatic dependency installation
- ✅ Built-in keep-alive server (prevents sleep)
- ✅ Environment variable management via Secrets
- ✅ 24/7 uptime with Always On (paid feature)

### Option 2: Local Installation

1. **Clone or download this repository**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment file**:
   - Copy `.env.example` to `.env`
   - Add both required values:
     ```
     TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
     AUTHORIZED_USER_ID=your_telegram_user_id_here
     ```
   - **Important**: Both values are **required**
   - See [How to Get Your User ID](HOW_TO_GET_USER_ID.md) for instructions

4. **Run the bot**:
   ```bash
   python bot.py
   ```

## 🔧 Build & Run Commands

### **Quick Start (Local)**

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and add your tokens

# 3. Run the bot
python bot.py
```

### **Replit Deployment**

```bash
# Setup (run once)
bash setup.sh

# Run (or click Run button)
python bot.py
```

### **Production (Background Process)**

```bash
# Using nohup
nohup python bot.py > bot.log 2>&1 &

# Using screen
screen -S purgebot
python bot.py
# Ctrl+A, D to detach

# Using systemd (Linux)
sudo systemctl start purgebot.service
```

### **Stop the Bot**

```bash
# Ctrl+C (if running in foreground)

# Kill background process
pkill -f "python bot.py"

# Or find PID and kill
ps aux | grep bot.py
kill <PID>
```

## Usage

### Starting the Bot

**On Replit**: Click the "Run" button

**Locally**: 
```bash
python bot.py
```

The bot will start and wait for incoming messages. On Replit, a keep-alive web server will also start on port 8080.

### File Format

Create a text file (`.txt`) with the following format:

```
# Comments are supported (lines starting with #)
production
api : your_bunny_cdn_api_key_here
https://cdn.example.com/image1.jpg
https://cdn.example.com/image2.jpg
https://cdn.example.com/styles.css

staging
api : another_api_key
https://cdn2.example.com/file1.js
https://cdn2.example.com/file2.png
```

**Format Rules:**
- **Account Name**: Any text (max 100 chars)
- **API Key Line**: `api : your_api_key` or `api: your_api_key` or `api = your_api_key`
  - API key must be 10-256 characters
- **URLs**: Must start with `http://` or `https://`
  - Max 2048 characters per URL
  - Max 10,000 URLs per account
- **Separators**: Blank line between accounts
- **Comments**: Lines starting with `#` are ignored
- **Encoding**: UTF-8, UTF-8-BOM, Latin-1, CP1252, or ISO-8859-1 supported
- **File Size**: Maximum 10MB

**What Gets Validated:**
✅ URL format and protocol
✅ API key length and presence
✅ Account structure
✅ File encoding
✅ Duplicate detection (coming soon)

### Using the Bot

1. **Start a chat** with your bot on Telegram
2. **Send** `/start` to see the welcome message
3. **Upload** your `.txt` file
4. **Wait** for the bot to process and receive detailed results

### Available Commands

**Basic Commands:**
- `/start` - Display welcome message and instructions
- `/help` - Show detailed help and file format examples
- `/dryrun` - Enable dry-run mode (test without purging)
- `/purge <url>` - Purge single URL without file upload
- `/cancel` - Stop ongoing purge
- `/resume` - List saved sessions or resume a specific session
- `/sessions` - View all your saved purge sessions

**New Features:**
- ✨ Inline buttons for pause/cancel during purge
- 📊 Visual progress bars with real-time ETA
- 🧪 Dry-run mode for validation before purging
- 🔗 Direct URL purge without file creation

## Security

### Single User Restriction (Required)

**This bot is configured for single-user access only.** You must provide your Telegram User ID for the bot to start:

1. **Get your Telegram User ID**:
   - Message [@userinfobot](https://t.me/userinfobot) on Telegram
   - Or see detailed instructions: [HOW_TO_GET_USER_ID.md](HOW_TO_GET_USER_ID.md)

2. **Add required secrets** to Replit Secrets:
   - Click on "Secrets" (🔒 icon) in the left sidebar
   - **Required**: `TELEGRAM_BOT_TOKEN` = Your bot token from BotFather
   - **Required**: `AUTHORIZED_USER_ID` = Your Telegram user ID (get from [@userinfobot](https://t.me/userinfobot))
   - See [How to Get Your User ID](HOW_TO_GET_USER_ID.md) for detailed instructions

3. **Restart the bot**

**What happens:**
- ✅ **You** (authorized user) can use all bot features normally
- 🚫 **Others** will see: "Access Denied - This bot is restricted to authorized users only"
- 📝 All unauthorized access attempts are logged with user IDs
- ⚠️ **Bot won't start** without `AUTHORIZED_USER_ID` set

## Security Best Practices

- **Never share your `.env` file** - it contains sensitive tokens
- **Keep your bot token private** - anyone with it can control your bot
- **Restrict bot access** - Use `AUTHORIZED_USER_ID` to limit to your account only
- **Bunny CDN API keys** are transmitted securely but stored in the uploaded file
- **Monitor logs** - Unauthorized access attempts are logged with user IDs
- Consider using a private Telegram group for added security
- Regularly check Replit Secrets or `.env` file for unauthorized changes

## Example Workflow

1. Create a file `purge_list.txt`:
   ```
   production
   api : abcd1234-5678-90ef-ghij-klmnopqrstuv
   https://cdn.mysite.com/images/banner.jpg
   https://cdn.mysite.com/css/main.css
   
   staging
   api : wxyz9876-5432-10ab-cdef-ghijklmnopqr
   https://staging.mysite.com/assets/logo.png
   ```

2. Open your Telegram bot
3. Upload `purge_list.txt`
4. Receive results showing which URLs were successfully purged

## API Reference

This bot uses the [Bunny CDN Purge API](https://docs.bunny.net/reference/purgepublic_indexpost):
- **Endpoint**: `POST https://api.bunny.net/purge`
- **Authentication**: API key via `AccessKey` header
- **Rate Limits**: Enforced by Bunny CDN (see [documentation](https://docs.bunny.net/docs/cdn-api-purge-rate-limits))

## Rate Limiting

The bot includes built-in rate limiting features:
- Default 100ms delay between purge requests
- Automatic 5-second wait when rate limited (HTTP 429)
- Handles retry-after headers from Bunny CDN

## Error Handling

The bot handles various error scenarios:
- **401 Unauthorized**: Invalid API key
- **429 Too Many Requests**: Rate limit exceeded
- **Timeout**: Network timeouts (30s per request)
- **Invalid Format**: Malformed input files

## Keep-Alive Mechanism (Replit)

When deployed on Replit, the bot includes a keep-alive web server that:
- Runs on port 8080
- Prevents Replit from putting the bot to sleep
- Provides health check endpoint at `/health`
- Automatically detects Replit environment and activates

The keep-alive server runs in a separate thread and doesn't interfere with the bot's operation.

## Project Structure

```
cachepurgeBot/
├── bot.py              # Main Telegram bot handler
├── bunny_cdn.py        # Bunny CDN API integration
├── parser.py           # File parser for purge configurations
├── keep_alive.py       # Keep-alive web server for Replit
├── setup.sh            # Setup script for dependencies
├── requirements.txt    # Python dependencies
├── .replit             # Replit configuration
├── replit.nix          # Replit Nix environment
├── .env                # Environment variables (create from .env.example)
├── .env.example        # Example environment file
├── .gitignore          # Git ignore rules
├── example_purge.txt   # Example input file
└── README.md           # This file
```

## Troubleshooting

### Bot doesn't start
- **Missing token**: Check that `TELEGRAM_BOT_TOKEN` is set in Secrets (Replit) or `.env` (Local)
- **Missing user ID**: Check that `AUTHORIZED_USER_ID` is set - **this is required**
- **Invalid user ID**: Must be a number (e.g., `123456789`), not text
- Verify the token is correct from BotFather
- Check logs for specific error messages

### Replit-specific issues
- **Bot goes to sleep**: Enable "Always On" in Replit (paid feature) or use an external ping service to hit the keep-alive endpoint
- **Dependencies not installed**: Run `bash setup.sh` or manually run `pip install -r requirements.txt`
- **Port conflicts**: The keep-alive server uses port 8080 by default

### Purge fails with 401 error
- Verify your Bunny CDN API key is correct
- Ensure the API key has purge permissions

### Rate limit errors (429)
- The bot will automatically retry after the specified delay
- Consider reducing the number of URLs per batch
- Check [Bunny CDN rate limits](https://docs.bunny.net/docs/cdn-api-purge-rate-limits)

### File parsing errors
- **Invalid encoding**: Save file as UTF-8 (most text editors support this)
- **No accounts found**: Check format - account name, then `api :` line, then URLs
- **Invalid URLs**: Must start with `http://` or `https://` and have valid domain
- **Invalid API key**: Must be 10-256 characters long
- **Malformed lines**: Check for extra spaces, special characters, or line breaks
- **Comments**: Use `#` at the start of a line for comments

**Common Issues:**
```
❌ Wrong:
api your_key_here          # Missing colon
www.example.com/file.jpg   # Missing http://

✅ Correct:
api : your_key_here
https://www.example.com/file.jpg
```

## License

MIT License - feel free to use and modify as needed.

## Support

For issues with:
- **This bot**: Check the troubleshooting section or modify the code
- **Bunny CDN API**: Visit [Bunny CDN Documentation](https://docs.bunny.net/)
- **Telegram Bot API**: Visit [Telegram Bot API Documentation](https://core.telegram.org/bots/api)

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.
