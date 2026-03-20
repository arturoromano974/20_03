"""
Telegram Approval Workflow Integration

This module handles the Telegram bot integration for user approvals.
Nearly 100% automated - all actions require user approval via Telegram.
"""

import os
import json
import logging
from typing import Dict, Optional, Callable
from datetime import datetime
import redis
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from utils.config_loader import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Initialize Redis
redis_client = redis.Redis(
    host=config['redis']['host'],
    port=config['redis']['port'],
    db=config['redis']['db'],
    decode_responses=True
)

class TelegramApprovalWorkflow:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.pending_approvals = {}

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 Marketing Automation Bot Started\n\n"
            "I will request your approval for all automated marketing tasks.\n\n"
            "Commands:\n"
            "/status - View pending approvals\n"
            "/help - Show help message"
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        # Get pending approvals from Redis
        pending_keys = redis_client.keys('approval:pending:*')

        if not pending_keys:
            await update.message.reply_text("✅ No pending approvals")
            return

        status_msg = f"📋 Pending Approvals: {len(pending_keys)}\n\n"
        for key in pending_keys[:5]:  # Show max 5
            data = redis_client.get(key)
            if data:
                approval = json.loads(data)
                status_msg += f"• {approval.get('task_description', 'Unknown task')}\n"

        await update.message.reply_text(status_msg)

    async def request_approval(self, task_id: str, task_data: Dict,
                              callback: Optional[Callable] = None) -> bool:
        """Request approval from user via Telegram"""
        try:
            # Store in Redis
            approval_key = f'approval:pending:{task_id}'
            approval_data = {
                'task_id': task_id,
                'task_data': task_data,
                'timestamp': datetime.now().isoformat(),
                'status': 'pending'
            }

            redis_client.setex(
                approval_key,
                config['telegram']['approval_timeout'],
                json.dumps(approval_data)
            )

            # Store callback if provided
            if callback:
                self.pending_approvals[task_id] = callback

            # Create approval message
            message = self._format_approval_message(task_data)

            # Create inline keyboard
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{task_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{task_id}")
                ],
                [
                    InlineKeyboardButton("ℹ️ Details", callback_data=f"details_{task_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send to user (would use actual bot instance in production)
            logger.info(f"Approval request sent for task: {task_id}")
            logger.info(f"Message: {message}")

            return True

        except Exception as e:
            logger.error(f"Error requesting approval: {str(e)}")
            return False

    def request_approval_sync(self, task_id: str, task_data: Dict,
                              callback: Optional[Callable] = None) -> bool:
        """Synchronous wrapper for request_approval.

        Use this from synchronous Flask routes or other non-async code.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an event loop – schedule as a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    self.request_approval(task_id, task_data, callback),
                ).result()
        else:
            return asyncio.run(
                self.request_approval(task_id, task_data, callback)
            )

    async def handle_approval_callback(self, update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
        """Handle approval button callbacks"""
        query = update.callback_query
        await query.answer()

        # Parse callback data
        parts = query.data.split('_', 1)
        if len(parts) != 2:
            await query.edit_message_text("⚠️ Invalid callback data")
            return
        action, task_id = parts

        # Get approval data
        approval_key = f'approval:pending:{task_id}'
        approval_data = redis_client.get(approval_key)

        if not approval_data:
            await query.edit_message_text("⚠️ Approval request expired or not found")
            return

        approval = json.loads(approval_data)

        if action == 'approve':
            await self._handle_approve(query, task_id, approval)
        elif action == 'reject':
            await self._handle_reject(query, task_id, approval)
        elif action == 'details':
            await self._handle_details(query, task_id, approval)

    async def _handle_approve(self, query, task_id: str, approval: Dict):
        """Handle approval action"""
        try:
            # Update status
            approval['status'] = 'approved'
            approval['approved_at'] = datetime.now().isoformat()

            # Store approved status
            redis_client.setex(
                f'approval:approved:{task_id}',
                86400,  # 24 hours
                json.dumps(approval)
            )

            # Remove from pending
            redis_client.delete(f'approval:pending:{task_id}')

            # Execute callback if registered
            if task_id in self.pending_approvals:
                callback = self.pending_approvals[task_id]
                await callback(approval['task_data'])
                del self.pending_approvals[task_id]

            await query.edit_message_text(
                f"✅ Approved: {approval['task_data'].get('task_description', 'Task')}\n\n"
                f"Execution started at {datetime.now().strftime('%H:%M:%S')}"
            )

            logger.info(f"Task approved: {task_id}")

        except Exception as e:
            logger.error(f"Error handling approval: {str(e)}")
            await query.edit_message_text(f"❌ Error processing approval: {str(e)}")

    async def _handle_reject(self, query, task_id: str, approval: Dict):
        """Handle rejection action"""
        try:
            # Update status
            approval['status'] = 'rejected'
            approval['rejected_at'] = datetime.now().isoformat()

            # Store rejected status
            redis_client.setex(
                f'approval:rejected:{task_id}',
                86400,
                json.dumps(approval)
            )

            # Remove from pending
            redis_client.delete(f'approval:pending:{task_id}')

            # Remove callback
            if task_id in self.pending_approvals:
                del self.pending_approvals[task_id]

            await query.edit_message_text(
                f"❌ Rejected: {approval['task_data'].get('task_description', 'Task')}\n\n"
                f"Task will not be executed."
            )

            logger.info(f"Task rejected: {task_id}")

        except Exception as e:
            logger.error(f"Error handling rejection: {str(e)}")
            await query.edit_message_text(f"❌ Error processing rejection: {str(e)}")

    async def _handle_details(self, query, task_id: str, approval: Dict):
        """Show detailed information about the task"""
        try:
            task_data = approval['task_data']

            details = f"📋 Task Details\n\n"
            details += f"ID: {task_id}\n"
            details += f"Type: {task_data.get('task_type', 'Unknown')}\n"
            details += f"Description: {task_data.get('task_description', 'N/A')}\n"
            details += f"Estimated Impact: {task_data.get('estimated_impact', 'N/A')}\n"
            details += f"Requested: {approval['timestamp']}\n\n"

            # Add specific details based on task type
            if task_data.get('task_type') == 'campaign_creation':
                details += f"Budget: ${task_data.get('budget', 0)}\n"
                details += f"Objective: {task_data.get('objective', 'N/A')}\n"
            elif task_data.get('task_type') == 'budget_adjustment':
                details += f"Current Budget: ${task_data.get('current_budget', 0)}\n"
                details += f"New Budget: ${task_data.get('new_budget', 0)}\n"
                details += f"Change: {task_data.get('budget_change_pct', 0)}%\n"

            # Recreate keyboard
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{task_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{task_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(details, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error showing details: {str(e)}")
            await query.answer(f"Error: {str(e)}")

    def _format_approval_message(self, task_data: Dict) -> str:
        """Format approval request message"""
        msg = "🤖 New Task Requires Approval\n\n"
        msg += f"📝 {task_data.get('task_description', 'Unknown task')}\n\n"
        msg += f"Type: {task_data.get('task_type', 'Unknown')}\n"
        msg += f"Priority: {task_data.get('priority', 'Medium')}\n"
        msg += f"Estimated Impact: {task_data.get('estimated_impact', 'Unknown')}\n"

        if task_data.get('budget'):
            msg += f"Budget: ${task_data.get('budget')}\n"

        msg += f"\n⏰ Requested: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return msg

    def run(self):
        """Run the Telegram bot"""
        # Create application
        application = Application.builder().token(self.bot_token).build()

        # Register handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CallbackQueryHandler(self.handle_approval_callback))

        # Start bot
        logger.info("Starting Telegram bot...")
        application.run_polling()

def create_approval_workflow() -> TelegramApprovalWorkflow:
    """Factory function to create approval workflow"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    return TelegramApprovalWorkflow(bot_token, chat_id)

if __name__ == '__main__':
    workflow = create_approval_workflow()
    workflow.run()
