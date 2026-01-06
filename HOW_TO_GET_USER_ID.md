# How to Get Your Telegram User ID

To restrict the bot to only your account, you need to find your Telegram User ID.

## Method 1: Using @userinfobot (Easiest)

1. Open Telegram
2. Search for `@userinfobot` in the search bar
3. Start a chat with the bot
4. Send any message to it
5. The bot will reply with your user information including your **User ID**
6. Copy the number (it will look like `123456789`)

## Method 2: Using @getidsbot

1. Open Telegram
2. Search for `@getidsbot`
3. Start a chat with the bot
4. Send `/start`
5. The bot will show your User ID
6. Copy the number

## Method 3: Using the Bot Itself (Temporary Setup)

1. **First**, set up the bot WITHOUT the `AUTHORIZED_USER_ID` environment variable
2. Start the bot
3. Send `/start` to your bot
4. Check the bot logs - it will show something like:
   ```
   Authorized access by user 123456789 (@your_username)
   ```
5. Copy your User ID from the logs
6. **Stop the bot**
7. Add `AUTHORIZED_USER_ID=123456789` to your `.env` file
8. Restart the bot

## Setting Up the Restriction

### For Local Development:

1. Create/edit `.env` file in the project root:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   AUTHORIZED_USER_ID=123456789
   ```

2. Replace `123456789` with your actual User ID

### For Replit:

1. Go to your Repl
2. Click on "Secrets" (🔒 icon) in the left sidebar
3. Add a new secret:
   - **Key**: `AUTHORIZED_USER_ID`
   - **Value**: `123456789` (your actual User ID)
4. Click "Add secret"
5. Restart the Repl

## Verification

Once configured:

1. **You** should be able to use all bot commands normally
2. **Others** who try to use the bot will see:
   ```
   🚫 Access Denied
   
   This bot is restricted to authorized users only.
   
   Your User ID: [their_id]
   
   If you believe this is an error, contact the bot administrator.
   ```

## Security Notes

- Your User ID is **not** sensitive information
- It's visible to anyone who can send you messages
- However, only share your bot token with trusted people
- The bot will log unauthorized access attempts with user IDs for your security

## Troubleshooting

**Bot rejects everyone (including you):**
- Check that `AUTHORIZED_USER_ID` is set correctly
- Verify it's a number without quotes in `.env`
- Check logs for "Bot restricted to user ID: [number]"

**Bot accepts everyone:**
- Check if `AUTHORIZED_USER_ID` is set in environment
- Logs should show: "AUTHORIZED_USER_ID not set - bot accessible to all users"
- Make sure you restarted the bot after adding the variable

**ValueError error on startup:**
- `AUTHORIZED_USER_ID` must be a plain number
- Don't use quotes: `AUTHORIZED_USER_ID=123456789` ✅
- Not: `AUTHORIZED_USER_ID="123456789"` ❌
