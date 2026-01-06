import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
from dotenv import load_dotenv
from parser import PurgeFileParser
from bunny_cdn import BunnyCDNPurger
from state_manager import PurgeStateManager

try:
    from keep_alive import keep_alive
    REPLIT_ENV = True
except ImportError:
    REPLIT_ENV = False

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states for direct URL purge
WAITING_FOR_API_KEY = 1

class CachePurgeBot:
    """Telegram bot for Bunny CDN cache purging."""
    
    def __init__(self, token: str, authorized_user_id: int):
        self.token = token
        self.authorized_user_id = authorized_user_id
        self.parser = PurgeFileParser()
        self.state_manager = PurgeStateManager()
        self.app = None
        self.active_purger = None
        self.cancel_event = asyncio.Event()
        self.pause_event = asyncio.Event()
        logger.info(f"Bot initialized with authorization for user ID: {authorized_user_id}")
    
    def is_authorized(self, user_id: int) -> bool:
        """
        Check if user is authorized to use the bot.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if authorized, False otherwise
        """
        return user_id == self.authorized_user_id
    
    async def check_authorization(self, update: Update) -> bool:
        """
        Check authorization and send rejection message if unauthorized.
        
        Args:
            update: Telegram update object
            
        Returns:
            True if authorized, False otherwise
        """
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        if not self.is_authorized(user_id):
            logger.warning(f"Unauthorized access attempt by user {user_id} (@{username})")
            await update.message.reply_text(
                "🚫 **Access Denied**\n\n"
                "This bot is restricted to authorized users only.\n\n"
                f"Your User ID: `{user_id}`\n\n"
                "If you believe this is an error, contact the bot administrator.",
                parse_mode='Markdown'
            )
            return False
        
        logger.info(f"Authorized access by user {user_id} (@{username})")
        return True
    
    def create_progress_bar(self, completed: int, total: int, length: int = 10) -> str:
        """Create a visual progress bar."""
        filled = int(length * completed / total) if total > 0 else 0
        bar = '█' * filled + '░' * (length - filled)
        percentage = int(100 * completed / total) if total > 0 else 0
        return f"[{bar}] {percentage}%"
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not await self.check_authorization(update):
            return
        welcome_message = (
            "🚀 **Bunny CDN Cache Purge Bot**\n\n"
            "**Features:**\n"
            "✅ Batch purge from files\n"
            "✅ Direct URL purge (no file needed)\n"
            "✅ Dry-run mode for testing\n"
            "✅ Pause/Cancel control\n"
            "✅ Auto-resume on errors\n"
            "✅ Real-time progress bars\n\n"
            "**Quick Start:**\n"
            "📤 Upload a .txt file to batch purge\n"
            "🔗 Use /purge <url> for single URL\n"
            "🧪 Use /dryrun before uploading to test\n\n"
            "Type /help for detailed instructions!"
        )
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not await self.check_authorization(update):
            return
        help_message = (
            "📖 **Command Reference:**\n\n"
            "**File-Based Purge:**\n"
            "• Upload .txt file → Start purge\n"
            "• Format: account name, api key, URLs\n\n"
            "**Direct URL Purge:**\n"
            "• `/purge <url>` - Purge single URL\n"
            "• Bot will ask for API key\n"
            "• Example: `/purge https://cdn.example.com/file.jpg`\n\n"
            "**Dry-Run Mode:**\n"
            "• `/dryrun` - Enable test mode\n"
            "• Upload file → See analysis without purging\n"
            "• Shows duplicates, estimates, validation\n\n"
            "**Session Management:**\n"
            "• `/resume` - List/resume saved sessions\n"
            "• `/sessions` - View all sessions\n"
            "• `/cancel` - Stop current purge\n\n"
            "**During Purge:**\n"
            "• Use inline buttons to Pause/Cancel\n"
            "• Progress bar shows real-time status\n"
            "• Speed and ETA displayed\n\n"
            "**File Format Example:**\n"
            "```\n"
            "production\n"
            "api : your_api_key\n"
            "https://cdn.example.com/file1.jpg\n"
            "https://cdn.example.com/file2.css\n"
            "```\n\n"
            "⚡ **Auto-Recovery:**\n"
            "If the bot encounters an error, your progress is automatically saved. "
            "Use /resume to continue from where you left off!"
        )
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def dryrun_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /dryrun command - enable dry-run mode."""
        if not await self.check_authorization(update):
            return
        
        context.user_data['dryrun_mode'] = True
        await update.message.reply_text(
            "🧪 **Dry-Run Mode Enabled**\n\n"
            "Upload your .txt file now.\n\n"
            "**What you'll see:**\n"
            "✅ File validation\n"
            "✅ Duplicate detection\n"
            "✅ Time estimates\n"
            "✅ Total API calls needed\n\n"
            "❌ No actual purging will happen\n\n"
            "💡 This helps you verify your configuration before the actual purge.",
            parse_mode='Markdown'
        )
    
    async def purge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /purge <url> command - direct URL purge."""
        if not await self.check_authorization(update):
            return
        
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "⚠️ **Usage:** `/purge <url>`\n\n"
                "**Example:**\n"
                "`/purge https://cdn.example.com/image.jpg`\n\n"
                "I'll ask for your API key next.",
                parse_mode='Markdown'
            )
            return
        
        url = context.args[0]
        
        # Validate URL
        is_valid, result = self.parser.validate_url(url)
        if not is_valid:
            await update.message.reply_text(
                f"❌ Invalid URL: {result}\n\n"
                "URL must start with http:// or https://",
                parse_mode='Markdown'
            )
            return
        
        # Store URL and ask for API key
        context.user_data['pending_direct_purge'] = {'url': url}
        
        await update.message.reply_text(
            f"🔗 **URL to purge:**\n`{url}`\n\n"
            f"🔑 Please reply with your Bunny CDN API key:",
            parse_mode='Markdown'
        )
        
        return WAITING_FOR_API_KEY
    
    async def receive_api_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive API key for direct URL purge."""
        if 'pending_direct_purge' not in context.user_data:
            await update.message.reply_text("❌ No pending purge. Use `/purge <url>` first.")
            return ConversationHandler.END
        
        api_key = update.message.text.strip()
        
        # Validate API key
        is_valid, error_msg = self.parser.validate_api_key(api_key)
        if not is_valid:
            await update.message.reply_text(
                f"❌ Invalid API key: {error_msg}\n\n"
                "Please send a valid API key or /cancel to abort."
            )
            return WAITING_FOR_API_KEY
        
        url = context.user_data['pending_direct_purge']['url']
        
        # Execute purge
        status_msg = await update.message.reply_text(
            f"🚀 **Purging URL...**\n`{url}`\n\n"
            "Please wait...",
            parse_mode='Markdown'
        )
        
        try:
            async with BunnyCDNPurger(concurrency=1) as purger:
                success, message, status_code = await purger.purge_url(url, api_key)
            
            if success:
                await status_msg.edit_text(
                    f"✅ **Purge Successful!**\n\n"
                    f"URL: `{url}`\n"
                    f"Status: {status_code}\n"
                    f"Message: {message}",
                    parse_mode='Markdown'
                )
            else:
                await status_msg.edit_text(
                    f"❌ **Purge Failed**\n\n"
                    f"URL: `{url}`\n"
                    f"Status: {status_code}\n"
                    f"Error: {message}",
                    parse_mode='Markdown'
                )
        
        except Exception as e:
            await status_msg.edit_text(
                f"❌ **Error:**\n`{str(e)}`",
                parse_mode='Markdown'
            )
        
        # Cleanup
        del context.user_data['pending_direct_purge']
        return ConversationHandler.END
    
    async def cancel_direct_purge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel direct URL purge conversation."""
        if 'pending_direct_purge' in context.user_data:
            del context.user_data['pending_direct_purge']
        
        await update.message.reply_text("❌ Direct purge cancelled.")
        return ConversationHandler.END
    
    async def cancel_purge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command - cancel ongoing purge."""
        if not await self.check_authorization(update):
            return
        
        if self.active_purger:
            self.cancel_event.set()
            await update.message.reply_text(
                "🛑 **Cancelling purge...**\n\n"
                "The purge will stop after the current batch.\n"
                "Your progress has been saved."
            )
        else:
            await update.message.reply_text(
                "ℹ️ No active purge to cancel."
            )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()
        
        if not await self.check_authorization(update):
            return
        
        if query.data == "start_purge":
            # User confirmed to start purge
            pending = context.user_data.get('pending_purge')
            if pending:
                accounts = pending['accounts']
                total_links = pending['total_links']
                
                await query.edit_message_text(
                    "🚀 Starting purge...",
                    parse_mode='Markdown'
                )
                
                await self.execute_purge(update, context, accounts, total_links)
                
                # Cleanup
                del context.user_data['pending_purge']
        
        elif query.data == "cancel_upload":
            # User cancelled the upload
            if 'pending_purge' in context.user_data:
                del context.user_data['pending_purge']
            
            await query.edit_message_text(
                "❌ Upload cancelled. No purge will be performed."
            )
        
        elif query.data == "pause_purge":
            # Pause ongoing purge
            if not self.pause_event.is_set():
                self.pause_event.set()
                await query.answer("⏸️ Purge paused. Click Resume to continue.", show_alert=True)
                # Update button
                keyboard = [
                    [
                        InlineKeyboardButton("▶️ Resume", callback_data="resume_purge"),
                        InlineKeyboardButton("🛑 Cancel", callback_data="cancel_purge")
                    ]
                ]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.answer("Already paused", show_alert=False)
        
        elif query.data == "resume_purge":
            # Resume paused purge
            if self.pause_event.is_set():
                self.pause_event.clear()
                await query.answer("▶️ Purge resumed!", show_alert=True)
                # Update button
                keyboard = [
                    [
                        InlineKeyboardButton("⏸️ Pause", callback_data="pause_purge"),
                        InlineKeyboardButton("🛑 Cancel", callback_data="cancel_purge")
                    ]
                ]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.answer("Not paused", show_alert=False)
        
        elif query.data == "cancel_purge":
            # Cancel ongoing purge
            self.cancel_event.set()
            await query.edit_message_text(
                "🛑 **Purge Cancelled**\n\n"
                "Progress has been saved.\n"
                "Use `/resume` to continue later if needed.",
                parse_mode='Markdown'
            )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads with robust error handling."""
        if not await self.check_authorization(update):
            return
        
        document = update.message.document
        
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text(
                "⚠️ Please send a .txt file containing your purge configuration.\n\n"
                "Supported format: `.txt` only"
            )
            return
        
        if document.file_size > 10 * 1024 * 1024:
            await update.message.reply_text(
                "⚠️ File too large! Maximum size is 10MB.\n\n"
                "Consider splitting into multiple files."
            )
            return
        
        processing_msg = await update.message.reply_text(
            "📥 File received! Processing...\n"
            f"📄 File: `{document.file_name}`\n"
            f"📦 Size: {document.file_size:,} bytes",
            parse_mode='Markdown'
        )
        
        try:
            file = await context.bot.get_file(document.file_id)
            file_content = await file.download_as_bytearray()
            
            content = None
            encoding_tried = []
            
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    content = file_content.decode(encoding)
                    logger.info(f"Successfully decoded file with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    encoding_tried.append(encoding)
                    continue
            
            if content is None:
                await processing_msg.edit_text(
                    f"❌ Unable to decode file. Tried encodings: {', '.join(encoding_tried)}\n\n"
                    "Please ensure your file is saved in UTF-8 encoding."
                )
                return
            
            try:
                accounts = self.parser.parse_file(content)
            except ValueError as e:
                await processing_msg.edit_text(
                    f"❌ **File Parsing Error**\n\n"
                    f"{str(e)}\n\n"
                    f"**Expected Format:**\n"
                    f"```\n"
                    f"account_name\n"
                    f"api : your_api_key\n"
                    f"https://cdn.example.com/file1.jpg\n"
                    f"https://cdn.example.com/file2.css\n"
                    f"\n"
                    f"another_account\n"
                    f"api : another_key\n"
                    f"https://cdn2.example.com/file.js\n"
                    f"```\n\n"
                    f"Use /help for more details.",
                    parse_mode='Markdown'
                )
                return
            
            if not accounts:
                await processing_msg.edit_text(
                    "❌ No valid accounts found in the file.\n\n"
                    "Please check:\n"
                    "✓ Each account has a name\n"
                    "✓ API key line starts with 'api :'\n"
                    "✓ URLs start with http:// or https://\n"
                    "✓ Blank line between accounts"
                )
                return
            
            summary = self.parser.get_parse_summary(accounts)
            total_links = sum(len(acc['links']) for acc in accounts)
            
            # Check if dry-run mode is requested
            is_dryrun = context.user_data.get('dryrun_mode', False)
            
            if is_dryrun:
                # Dry-run mode - just show analysis
                context.user_data['dryrun_mode'] = False
                
                # Calculate stats
                all_urls = [url for acc in accounts for url in acc['links']]
                unique_urls = list(dict.fromkeys(all_urls))
                duplicates = len(all_urls) - len(unique_urls)
                
                est_time_min = int(total_links / 5)
                est_time_max = int(total_links / 3)
                
                await processing_msg.edit_text(
                    f"🧪 **Dry-Run Analysis**\n\n"
                    f"{summary}\n\n"
                    f"📊 **Statistics:**\n"
                    f"• Total URLs: {total_links}\n"
                    f"• Unique URLs: {len(unique_urls)}\n"
                    f"• Duplicates: {duplicates}\n"
                    f"• Accounts: {len(accounts)}\n\n"
                    f"⏱️ **Estimated Time:** {est_time_min}-{est_time_max} seconds\n"
                    f"⚡ **API Calls:** ~{total_links} requests\n\n"
                    f"✅ No issues detected. Ready to purge!\n\n"
                    f"💡 Upload the file again normally to start the actual purge.",
                    parse_mode='Markdown'
                )
                return
            
            # Show confirmation with action buttons
            keyboard = [
                [
                    InlineKeyboardButton("🚀 Start Purge", callback_data="start_purge"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_upload")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(
                f"✅ **File Parsed Successfully!**\n\n{summary}\n\n"
                f"⏱️ Estimated time: ~{int(total_links / 5)}-{int(total_links / 3)} seconds\n\n"
                f"Ready to start?",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            # Store accounts in context for callback
            context.user_data['pending_purge'] = {
                'accounts': accounts,
                'total_links': total_links,
                'message_id': processing_msg.message_id
            }
            return
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            try:
                await processing_msg.edit_text(
                    f"❌ **Unexpected Error**\n\n"
                    f"Error: `{str(e)}`\n\n"
                    "Please check your file and try again. "
                    "If the issue persists, contact support.",
                    parse_mode='Markdown'
                )
            except:
                await update.message.reply_text(
                    f"❌ Error: {str(e)}\n\n"
                    "Please check your file format and try again."
                )
    
    async def send_results(self, update: Update, results: dict):
        """Send purge results to user."""
        for account_name, account_results in results.items():
            success_count = sum(1 for _, success, _ in account_results if success)
            fail_count = len(account_results) - success_count
            
            summary = (
                f"📊 **Results for {account_name}:**\n"
                f"✅ Success: {success_count}\n"
                f"❌ Failed: {fail_count}\n"
                f"📝 Total: {len(account_results)}\n\n"
            )
            
            details = []
            for url, success, message in account_results:
                details.append(message)
            
            full_message = summary + "\n".join(details)
            
            if len(full_message) > 4000:
                await update.message.reply_text(summary, parse_mode='Markdown')
                
                chunks = []
                current_chunk = ""
                for detail in details:
                    if len(current_chunk) + len(detail) + 1 > 4000:
                        chunks.append(current_chunk)
                        current_chunk = detail
                    else:
                        current_chunk += "\n" + detail if current_chunk else detail
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(full_message, parse_mode='Markdown')
        
        await update.message.reply_text("✨ All done!")
    
    async def resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command."""
        if not await self.check_authorization(update):
            return
        
        user_id = update.effective_user.id
        
        if context.args and len(context.args) > 0:
            session_id = context.args[0]
            await self.resume_session(update, session_id)
        else:
            sessions = self.state_manager.list_sessions(user_id)
            
            if not sessions:
                await update.message.reply_text(
                    "🤷 No saved sessions found.\n\n"
                    "Sessions are created automatically when a purge is interrupted."
                )
                return
            
            message = "📚 **Your Saved Sessions:**\n\n"
            
            for i, session in enumerate(sessions[:5], 1):
                info = self.state_manager.get_resume_info(session['session_id'])
                if info:
                    message += (
                        f"{i}. `{session['session_id']}`\n"
                        f"   ⏱️ {info['timestamp'][:19]}\n"
                        f"   📊 Progress: {info['completed']}/{info['total_urls']} "
                        f"({info['progress_percent']}%)\n"
                        f"   ⚠️ Failed: {info['failed']}\n\n"
                    )
            
            message += "\nUse `/resume <session_id>` to continue a session."
            await update.message.reply_text(message, parse_mode='Markdown')
    
    async def sessions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sessions command."""
        if not await self.check_authorization(update):
            return
        await self.resume_command(update, context)
    
    async def resume_session(self, update: Update, session_id: str):
        """Resume a purge session."""
        state = self.state_manager.load_state(session_id)
        
        if not state:
            await update.message.reply_text(
                f"❌ Session `{session_id}` not found.\n\n"
                "Use /sessions to see available sessions.",
                parse_mode='Markdown'
            )
            return
        
        info = self.state_manager.get_resume_info(session_id)
        
        await update.message.reply_text(
            f"🔄 **Resuming Session**\n\n"
            f"📊 Progress: {info['completed']}/{info['total_urls']} ({info['progress_percent']}%)\n"
            f"✅ Completed: {info['completed']}\n"
            f"⚠️ Failed: {info['failed']}\n"
            f"🕒 Remaining: {info['remaining']}\n\n"
            f"🚀 Continuing...",
            parse_mode='Markdown'
        )
        
        try:
            import time
            start_time = time.time()
            accounts = state['accounts']
            
            status_message = await update.message.reply_text(
                f"🚀 Resuming purge...\n"
                f"💾 Session: `{session_id}`",
                parse_mode='Markdown'
            )
            
            progress_updates = {'last_update': 0}
            
            async def progress_callback(account: str, completed: int, total: int):
                current_time = time.time()
                if current_time - progress_updates['last_update'] >= 3:
                    elapsed = current_time - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (total - completed) / rate if rate > 0 else 0
                    
                    try:
                        await status_message.edit_text(
                            f"📊 **Account: {account}**\n"
                            f"✅ Progress: {completed}/{total} ({int(completed/total*100)}%)\n"
                            f"⚡ Speed: {rate:.1f} URLs/sec\n"
                            f"⏱️ Time remaining: ~{int(remaining)}s",
                            parse_mode='Markdown'
                        )
                        progress_updates['last_update'] = current_time
                    except Exception as e:
                        logger.warning(f"Failed to update progress: {e}")
            
            async with BunnyCDNPurger(
                concurrency=15,
                state_manager=self.state_manager,
                session_id=session_id
            ) as purger:
                results = await purger.purge_accounts(accounts, progress_callback, resume_state=state)
            
            elapsed_total = time.time() - start_time
            await status_message.edit_text(
                f"✅ **Resume Complete!**\n"
                f"⏱️ Time: {elapsed_total:.1f}s\n\n"
                f"📊 Generating report...",
                parse_mode='Markdown'
            )
            
            await self.send_results(update, results)
            
            self.state_manager.delete_state(session_id)
            await update.message.reply_text(
                f"✅ Session `{session_id}` completed and removed.",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error resuming session: {e}")
            await update.message.reply_text(
                f"❌ Error resuming session: {str(e)}\n\n"
                "Your progress is still saved. Try again later."
            )
    
    async def execute_purge(self, update: Update, context: ContextTypes.DEFAULT_TYPE, accounts: list, total_links: int):
        """Execute the purge with enhanced progress UI and control buttons."""
        import time
        start_time = time.time()
        user_id = update.effective_user.id
        session_id = self.state_manager.generate_session_id(user_id)
        
        # Reset flags
        self.cancel_event.clear()
        self.pause_event.clear()
        
        # Control buttons
        control_keyboard = [
            [
                InlineKeyboardButton("⏸️ Pause", callback_data="pause_purge"),
                InlineKeyboardButton("🛑 Cancel", callback_data="cancel_purge")
            ]
        ]
        control_markup = InlineKeyboardMarkup(control_keyboard)
        
        status_message = await update.effective_chat.send_message(
            f"✅ Starting purge for {len(accounts)} account(s)\n"
            f"📊 Total URLs: **{total_links}**\n"
            f"💾 Session: `{session_id}`\n\n"
            f"{self.create_progress_bar(0, total_links)}\n\n"
            f"Use buttons below to control the purge.",
            parse_mode='Markdown',
            reply_markup=control_markup
        )
        
        progress_updates = {'last_update': 0}
        
        async def progress_callback(account: str, completed: int, total: int):
            """Enhanced progress callback with pause/cancel and progress bar."""
            # Check for pause
            while self.pause_event.is_set():
                await asyncio.sleep(0.5)
            
            # Check for cancel
            if self.cancel_event.is_set():
                raise Exception("Purge cancelled by user")
            
            current_time = time.time()
            if current_time - progress_updates['last_update'] >= 2:
                elapsed = current_time - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                remaining = (total - completed) / rate if rate > 0 else 0
                
                progress_bar = self.create_progress_bar(completed, total, length=15)
                
                try:
                    await status_message.edit_text(
                        f"📊 **Purging: {account}**\n\n"
                        f"{progress_bar}\n\n"
                        f"✅ Completed: {completed}/{total}\n"
                        f"⚡ Speed: {rate:.1f} URLs/sec\n"
                        f"⏱️ Remaining: ~{int(remaining)}s\n"
                        f"💾 Session: `{session_id}`",
                        parse_mode='Markdown',
                        reply_markup=control_markup
                    )
                    progress_updates['last_update'] = current_time
                except Exception as e:
                    logger.warning(f"Failed to update progress: {e}")
        
        try:
            async with BunnyCDNPurger(
                concurrency=15,
                state_manager=self.state_manager,
                session_id=session_id
            ) as purger:
                self.active_purger = purger
                results = await purger.purge_accounts(accounts, progress_callback)
                self.active_purger = None
            
            elapsed_total = time.time() - start_time
            await status_message.edit_text(
                f"✅ **Purge Complete!**\n\n"
                f"{self.create_progress_bar(total_links, total_links)}\n\n"
                f"⏱️ Total time: {elapsed_total:.1f}s\n"
                f"⚡ Average speed: {total_links/elapsed_total:.1f} URLs/sec\n\n"
                f"📊 Generating detailed report...",
                parse_mode='Markdown'
            )
            
            await self.send_results(update, results)
            self.state_manager.delete_state(session_id)
        
        except Exception as e:
            self.active_purger = None
            logger.error(f"Error during purge: {e}")
            
            if "cancelled" in str(e).lower():
                await status_message.edit_text(
                    f"🛑 **Purge Cancelled**\n\n"
                    f"Progress saved to session: `{session_id}`\n\n"
                    f"Use `/resume {session_id}` to continue later.",
                    parse_mode='Markdown'
                )
            else:
                await update.effective_chat.send_message(
                    f"❌ **Error occurred!**\n\n"
                    f"Error: {str(e)}\n\n"
                    f"💾 Session: `{session_id}`\n"
                    f"Use `/resume {session_id}` to retry.",
                    parse_mode='Markdown'
                )
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages."""
        if not await self.check_authorization(update):
            return
        
        # Check if waiting for API key in conversation
        if 'pending_direct_purge' in context.user_data:
            return  # Let ConversationHandler handle it
        
        await update.message.reply_text(
            "Please send a .txt file with your purge configuration.\n"
            "Use /help to see the file format."
        )
    
    def run(self):
        """Start the bot."""
        self.app = Application.builder().token(self.token).build()
        
        # Conversation handler for direct URL purge
        purge_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("purge", self.purge_command)],
            states={
                WAITING_FOR_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_api_key)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_direct_purge)]
        )
        
        # Add all handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("dryrun", self.dryrun_command))
        self.app.add_handler(purge_conv_handler)
        self.app.add_handler(CommandHandler("cancel", self.cancel_purge_command))
        self.app.add_handler(CommandHandler("resume", self.resume_command))
        self.app.add_handler(CommandHandler("sessions", self.sessions_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_query))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        logger.info("Bot started successfully with all enhanced features!")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Main entry point."""
    if REPLIT_ENV:
        logger.info("Running in Replit environment - starting keep-alive server")
        keep_alive()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with your bot token or add to Replit Secrets.")
        return
    
    authorized_user_id = os.getenv('AUTHORIZED_USER_ID')
    if not authorized_user_id:
        logger.error("AUTHORIZED_USER_ID not found in environment variables!")
        logger.error("This bot requires user restriction for security.")
        logger.error("Please add your Telegram User ID to .env or Replit Secrets.")
        logger.error("Get your User ID from @userinfobot on Telegram.")
        return
    
    try:
        authorized_user_id = int(authorized_user_id)
        logger.info(f"Bot restricted to user ID: {authorized_user_id}")
    except ValueError:
        logger.error("AUTHORIZED_USER_ID must be a valid integer (Telegram user ID)")
        logger.error("Example: AUTHORIZED_USER_ID=123456789")
        return
    
    bot = CachePurgeBot(token, authorized_user_id)
    bot.run()

if __name__ == "__main__":
    main()
