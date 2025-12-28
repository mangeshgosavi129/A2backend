import json
import logging
from typing import Mapping, Tuple
import requests
from .config import config
# Setup logger
logger = logging.getLogger(__name__)

def _api_url() -> str:
    return f"https://graph.facebook.com/{config.VERSION}/{config.PHONE_NUMBER_ID}/messages"

def _get_text_payload(recipient: str, text: str) -> str:
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def send_whatsapp_text(
    to: str, 
    text: str
) -> Tuple[Mapping, int]:
    """
    Sends a WhatsApp message.
    
    Arguments:
        to (str): The recipient's phone number.
        text (str): The message body.
        config (WhatsAppSendConfig, optional): Dependency injection for config.
    """
    recipient = to
    
    # Validation
    if not (config.ACCESS_TOKEN and config.VERSION and config.PHONE_NUMBER_ID and recipient):
        logger.error("Missing WhatsApp configuration or recipient")
        return {"status": "error", "message": "Missing configuration"}, 500

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {config.ACCESS_TOKEN}",
    }

    try:
        # Timeout increased to 15s
        resp = requests.post(
            _api_url(), 
            data=_get_text_payload(recipient, text), 
            headers=headers, 
            timeout=15
        )
        resp.raise_for_status()
        return resp.json(), resp.status_code

    except requests.Timeout:
        logger.error("WhatsApp request timed out")
        return {"status": "error", "message": "Request timed out"}, 408

    except requests.RequestException as e:
        logger.error(f"WhatsApp send error: {e}")
        
        if 'resp' in locals():
             try:
                 return resp.json(), resp.status_code
             except Exception:
                 pass # Fall through to generic error
        return {"status": "error", "message": "Failed to send message"}, 500

def send_task_notification(phone: str, task_dict: dict) -> Tuple[Mapping, int]:
    """
    Sends a WhatsApp notification when a task is assigned to a user.
    """
    # Format the notification message
    message = f"📋 *New Task Assigned*\n\n"
    message += f"*Title:* {task_dict.get('title', 'N/A')}\n"
    
    if task_dict.get('description'):
        message += f"*Description:* {task_dict['description']}\n"
    
    message += f"*Priority:* {task_dict.get('priority', 'medium').upper()}\n"
    
    if task_dict.get('deadline'):
        message += f"*Deadline:* {task_dict['deadline']}\n"
    
    message += f"\nTask ID: #{task_dict.get('id', 'N/A')}"
    
    # Send the notification
    return send_whatsapp_text(phone, message)

def send_task_update_notification(phone: str, task_dict: dict) -> Tuple[Mapping, int]:
    """
    Sends a WhatsApp notification when a task is updated.
    """
    # Format the notification message
    message = f"📝 *Task Updated*\n\n"
    message += f"*Title:* {task_dict.get('title', 'N/A')}\n"
    
    if task_dict.get('description'):
        message += f"*Description:* {task_dict['description']}\n"
    
    message += f"*Status:* {task_dict.get('status', 'N/A').upper()}\n"
    message += f"*Priority:* {task_dict.get('priority', 'medium').upper()}\n"
    
    if task_dict.get('deadline'):
        message += f"*Deadline:* {task_dict['deadline']}\n"
    
    message += f"\nTask ID: #{task_dict.get('id', 'N/A')}"
    
    # Send the notification
    return send_whatsapp_text(phone, message)

def send_task_cancellation_notification(phone: str, task_dict: dict) -> Tuple[Mapping, int]:
    """
    Sends a WhatsApp notification when a task is cancelled.
    """
    # Format the notification message
    message = f"❌ *Task Cancelled*\n\n"
    message += f"*Title:* {task_dict.get('title', 'N/A')}\n"
    
    if task_dict.get('cancellation_reason'):
        message += f"*Reason:* {task_dict['cancellation_reason']}\n"
    
    message += f"\nTask ID: #{task_dict.get('id', 'N/A')}"
    
    # Send the notification
    return send_whatsapp_text(phone, message)


# =========================================================
# DEADLINE REMINDER NOTIFICATIONS
# =========================================================
def send_deadline_warning_notification(phone: str, task_dict: dict) -> Tuple[Mapping, int]:
    """
    60-min warning: Wrap it up fast, deadline almost here!
    """
    message = f"⏰ *Deadline Reminder*\n\n"
    message += f"*Task:* {task_dict.get('title', 'N/A')}\n"
    message += f"*Deadline:* {task_dict.get('deadline', 'N/A')}\n\n"
    message += f"⚡ Time to wrap it up – less than an hour left!\n"
    message += f"\nTask ID: #{task_dict.get('id', 'N/A')}"
    
    return send_whatsapp_text(phone, message)


def send_deadline_imminent_notification(phone: str, task_dict: dict) -> Tuple[Mapping, int]:
    """
    10-min reminder: Tell me to mark it complete if you're done.
    """
    message = f"🔔 *Almost There!*\n\n"
    message += f"*Task:* {task_dict.get('title', 'N/A')}\n"
    message += f"*Deadline:* {task_dict.get('deadline', 'N/A')}\n\n"
    message += f"📝 Done with this? Just reply 'mark task #{task_dict.get('id', 'N/A')} as completed'\n"
    message += f"\nTask ID: #{task_dict.get('id', 'N/A')}"
    
    return send_whatsapp_text(phone, message)


def send_deadline_crossed_notification(phone: str, task_dict: dict) -> Tuple[Mapping, int]:
    """
    Minimal overdue notice.
    """
    message = f"⌛ Task #{task_dict.get('id', 'N/A')} deadline crossed.\n"
    message += f"*{task_dict.get('title', 'N/A')}*"
    
    return send_whatsapp_text(phone, message)


# =========================================================
# DAILY SUMMARY REPORTS
# =========================================================
def _format_deadline_urgency(deadline_str: str) -> str:
    """Format deadline with urgency indicator emoji."""
    if not deadline_str:
        return "No deadline"
    
    from datetime import datetime
    import pytz
    
    try:
        deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        if deadline.tzinfo is None:
            deadline = ist.localize(deadline)
        else:
            deadline = deadline.astimezone(ist)
        
        delta = deadline - now
        hours = delta.total_seconds() / 3600
        
        if hours < 0:
            return f"🔴 OVERDUE"
        elif hours < 6:
            return f"🔴 {int(hours)}h left"
        elif hours < 24:
            return f"🟡 Today {deadline.strftime('%I:%M %p')}"
        elif hours < 48:
            return f"🟡 Tomorrow {deadline.strftime('%I:%M %p')}"
        else:
            return f"🟢 {deadline.strftime('%b %d')}"
    except:
        return deadline_str[:16] if len(deadline_str) > 16 else deadline_str


def _get_today_date_str() -> str:
    """Get today's date formatted nicely."""
    from datetime import datetime
    import pytz
    
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    return now.strftime('%b %d')


def send_personal_daily_report(phone: str, report_data: dict) -> Tuple[Mapping, int]:
    """
    Personal Task Report - sent to all users.
    Shows: completed today, due tasks, their progress updates.
    """
    user_name = report_data.get('user', {}).get('name', 'there')
    completed = report_data.get('completed_today', [])
    due_tasks = report_data.get('due_tasks', [])
    my_updates = report_data.get('my_updates_today', [])
    
    date_str = _get_today_date_str()
    
    # Build message
    message = f"📊 *Your Daily Summary* — {date_str}\n"
    message += f"Hey {user_name}! Here's your day at a glance:\n\n"
    
    # Section 1: Completed Today
    if completed:
        message += f"✅ *Completed Today* ({len(completed)})\n"
        for task in completed[:5]:  # Max 5 to keep message short
            message += f"• {task.get('title', 'Untitled')}\n"
        if len(completed) > 5:
            message += f"  _...and {len(completed) - 5} more_\n"
        message += "\n"
    
    # Section 2: Upcoming Deadlines
    if due_tasks:
        message += f"📋 *Your Tasks* ({len(due_tasks)})\n"
        for task in due_tasks[:7]:  # Max 7
            urgency = _format_deadline_urgency(task.get('deadline'))
            message += f"{urgency} {task.get('title', 'Untitled')}\n"
        if len(due_tasks) > 7:
            message += f"  _...and {len(due_tasks) - 7} more_\n"
        message += "\n"
    
    # Section 3: Your Updates
    if my_updates:
        message += f"📝 *Your Updates Today*\n"
        for update in my_updates[:3]:
            progress = update.get('progress_description', '')[:50]
            if len(update.get('progress_description', '')) > 50:
                progress += "..."
            message += f"• \"{progress}\" on _{update.get('title', 'task')}_\n"
        message += "\n"
    
    # Empty state
    if not completed and not due_tasks:
        message += "🎉 No tasks on your plate right now!\n\n"
    
    message += "—\n_Reply anytime to manage your tasks!_"
    
    return send_whatsapp_text(phone, message)


def send_assigned_daily_report(phone: str, report_data: dict) -> Tuple[Mapping, int]:
    """
    Assigned Task Report - sent to managers/owners.
    Shows: tasks they assigned, progress from team.
    """
    user_name = report_data.get('user', {}).get('name', 'there')
    assigned_tasks = report_data.get('assigned_tasks', [])
    updates_received = report_data.get('updates_received', [])
    
    date_str = _get_today_date_str()
    
    # Build message
    message = f"📋 *Tasks You've Assigned* — {date_str}\n\n"
    
    # Section 1: Team Progress
    if assigned_tasks:
        message += f"👥 *Team Progress* ({len(assigned_tasks)} tasks)\n"
        for task in assigned_tasks[:8]:  # Max 8
            assignees = task.get('assignee_names', [])
            assignee_str = ', '.join(assignees[:2]) if assignees else 'Unassigned'
            if len(assignees) > 2:
                assignee_str += f" +{len(assignees) - 2}"
            
            progress = task.get('progress_percentage', 0)
            urgency = _format_deadline_urgency(task.get('deadline'))
            
            # Status indicator
            if progress >= 80:
                status_icon = "🟢"
            elif progress >= 40:
                status_icon = "🟡"
            else:
                status_icon = "⚪"
            
            message += f"{status_icon} *{task.get('title', 'Untitled')}*\n"
            message += f"   {assignee_str} • {progress}% • {urgency}\n"
        
        if len(assigned_tasks) > 8:
            message += f"   _...and {len(assigned_tasks) - 8} more tasks_\n"
        message += "\n"
    
    # Section 2: Updates Received
    if updates_received:
        message += f"📬 *Updates Today*\n"
        for update in updates_received[:4]:
            assignees = update.get('assignee_names', ['Someone'])
            assignee = assignees[0] if assignees else 'Someone'
            progress = update.get('progress_description', '')[:40]
            if len(update.get('progress_description', '')) > 40:
                progress += "..."
            message += f"• {assignee} on _{update.get('title', 'task')}_:\n"
            message += f"  \"{progress}\"\n"
        message += "\n"
    
    # Empty state
    if not assigned_tasks:
        message += "_No active tasks assigned by you._\n\n"
    
    message += "—\n_No action needed, just keeping you in sync!_"
    
    return send_whatsapp_text(phone, message)
