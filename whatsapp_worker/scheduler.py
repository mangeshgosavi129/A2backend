"""
Deadline Reminder Scheduler

Periodically checks for tasks approaching their deadline and sends
WhatsApp notifications to assigned users.
"""
import logging
from datetime import datetime
from typing import Dict, Set
import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler

from .scheduler_config import (
    REMINDER_60_MIN, 
    REMINDER_10_MIN, 
    SCHEDULER_CHECK_INTERVAL,
    DAILY_REPORT_HOUR,
    DAILY_REPORT_MINUTE
)
from .send import (
    send_deadline_warning_notification,
    send_deadline_imminent_notification,
    send_deadline_crossed_notification,
    send_personal_daily_report,
    send_assigned_daily_report
)

logger = logging.getLogger(__name__)

# In-memory tracking of sent reminders (task_id -> set of reminder types sent)
# Format: {task_id: {'60min', '10min', 'overdue'}}
sent_reminders: Dict[int, Set[str]] = {}


def _get_tasks_with_deadlines() -> list:
    """Fetch active tasks with deadlines from internal API."""
    try:
        resp = requests.get(
            "http://localhost:8000/internals/tasks-with-deadlines",
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch tasks with deadlines: {e}")
        return []


def _should_send_reminder(task_id: int, reminder_type: str) -> bool:
    """Check if this reminder was already sent for this task."""
    if task_id not in sent_reminders:
        return True
    return reminder_type not in sent_reminders[task_id]


def _mark_reminder_sent(task_id: int, reminder_type: str):
    """Mark a reminder as sent to prevent duplicates."""
    if task_id not in sent_reminders:
        sent_reminders[task_id] = set()
    sent_reminders[task_id].add(reminder_type)


def _cleanup_completed_tasks(active_task_ids: Set[int]):
    """Remove tracking for tasks that are no longer active."""
    global sent_reminders
    sent_reminders = {
        tid: reminders 
        for tid, reminders in sent_reminders.items() 
        if tid in active_task_ids
    }


def check_deadlines():
    """
    Main job: Check all tasks with deadlines and send appropriate reminders.
    
    Called periodically by the scheduler.
    """
    logger.info("🔍 Checking task deadlines for reminders...")
    
    tasks = _get_tasks_with_deadlines()
    if not tasks:
        logger.info("No tasks with upcoming deadlines found")
        return
    
    ist_tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_tz)
    
    active_task_ids = set()
    
    for task in tasks:
        task_id = task.get('id')
        deadline_str = task.get('deadline')
        assignees = task.get('assignees', [])
        
        if not task_id or not deadline_str or not assignees:
            continue
        
        active_task_ids.add(task_id)
        
        # Parse deadline
        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            if deadline.tzinfo is None:
                deadline = ist_tz.localize(deadline)
            else:
                deadline = deadline.astimezone(ist_tz)
        except Exception as e:
            logger.warning(f"Could not parse deadline for task {task_id}: {e}")
            continue
        
        time_until_deadline = deadline - now
        minutes_until = time_until_deadline.total_seconds() / 60
        
        task_dict = {
            'id': task_id,
            'title': task.get('title', 'Untitled'),
            'deadline': deadline.strftime('%Y-%m-%d %H:%M')
        }
        
        # Determine which reminder to send
        notification_func = None
        reminder_type = None
        
        if minutes_until <= 0:
            # Deadline crossed
            if _should_send_reminder(task_id, 'overdue'):
                notification_func = send_deadline_crossed_notification
                reminder_type = 'overdue'
                logger.info(f"Task {task_id}: Deadline crossed, sending overdue notice")
        elif minutes_until <= REMINDER_10_MIN:
            # 10-min reminder
            if _should_send_reminder(task_id, '10min'):
                notification_func = send_deadline_imminent_notification
                reminder_type = '10min'
                logger.info(f"Task {task_id}: Within 10 minutes, sending imminent reminder")
        elif minutes_until <= REMINDER_60_MIN:
            # 60-min warning
            if _should_send_reminder(task_id, '60min'):
                notification_func = send_deadline_warning_notification
                reminder_type = '60min'
                logger.info(f"Task {task_id}: Within 60 minutes, sending warning")
        
        # Send notification to all assignees
        if notification_func and reminder_type:
            for assignee in assignees:
                phone = assignee.get('phone')
                if phone:
                    try:
                        result, status_code = notification_func(phone, task_dict)
                        if status_code == 200:
                            logger.info(f"✅ Sent {reminder_type} reminder for task {task_id} to {phone}")
                        else:
                            logger.error(f"❌ Failed to send reminder: {result}")
                    except Exception as e:
                        logger.error(f"Error sending reminder to {phone}: {e}")
            
            _mark_reminder_sent(task_id, reminder_type)
    
    # Cleanup old tracking data
    _cleanup_completed_tasks(active_task_ids)
    
    logger.info(f"✅ Deadline check complete. Processed {len(tasks)} tasks")


# Global scheduler instance
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))


def start_scheduler():
    """Start all scheduler jobs: deadline reminders and daily reports."""
    # Job 1: Deadline reminders (runs every minute)
    scheduler.add_job(
        check_deadlines,
        'interval',
        seconds=SCHEDULER_CHECK_INTERVAL,
        id='deadline_reminder_job',
        replace_existing=True
    )
    
    # Job 2: Daily summary reports (runs at 5 PM IST)
    scheduler.add_job(
        send_daily_reports,
        'cron',
        hour=DAILY_REPORT_HOUR,
        minute=DAILY_REPORT_MINUTE,
        id='daily_reports_job',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"🚀 Scheduler started: deadline reminders (every {SCHEDULER_CHECK_INTERVAL}s) + daily reports (at {DAILY_REPORT_HOUR}:{DAILY_REPORT_MINUTE:02d})")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("🛑 Scheduler stopped")


# =========================================================
# DAILY SUMMARY REPORTS (5 PM)
# =========================================================
def _get_users_for_daily_reports() -> list:
    """Fetch all users with roles for daily report distribution."""
    try:
        resp = requests.get(
            "http://localhost:8000/internals/users-for-daily-reports",
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch users for daily reports: {e}")
        return []


def _get_personal_report_data(user_id: int) -> dict:
    """Fetch personal report data for a user."""
    try:
        resp = requests.get(
            f"http://localhost:8000/internals/daily-personal-report/{user_id}",
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch personal report for user {user_id}: {e}")
        return {}


def _get_assigned_report_data(user_id: int) -> dict:
    """Fetch assigned tasks report data for a user."""
    try:
        resp = requests.get(
            f"http://localhost:8000/internals/daily-assigned-report/{user_id}",
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch assigned report for user {user_id}: {e}")
        return {}


def send_daily_reports():
    """
    Send daily summary reports at 5 PM IST.
    
    - All users get Personal Report
    - Manager/Owner also get Assigned Report (2 messages)
    """
    logger.info("📊 Starting daily summary reports...")
    
    users = _get_users_for_daily_reports()
    if not users:
        logger.info("No users found for daily reports")
        return
    
    reports_sent = 0
    errors = 0
    
    for user in users:
        user_id = user.get('id')
        phone = user.get('phone')
        can_assign = user.get('can_assign', False)
        name = user.get('name', 'User')
        
        if not user_id or not phone:
            continue
        
        # 1. Send Personal Report to everyone
        try:
            personal_data = _get_personal_report_data(user_id)
            if personal_data and 'error' not in personal_data:
                result, status_code = send_personal_daily_report(phone, personal_data)
                if status_code == 200:
                    logger.info(f"✅ Personal report sent to {name} ({phone})")
                    reports_sent += 1
                else:
                    logger.error(f"❌ Failed to send personal report to {name}: {result}")
                    errors += 1
        except Exception as e:
            logger.error(f"Error sending personal report to {name}: {e}")
            errors += 1
        
        # 2. Send Assigned Report to managers/owners only
        if can_assign:
            try:
                assigned_data = _get_assigned_report_data(user_id)
                if assigned_data and 'error' not in assigned_data:
                    # Only send if they have assigned tasks
                    if assigned_data.get('assigned_tasks'):
                        result, status_code = send_assigned_daily_report(phone, assigned_data)
                        if status_code == 200:
                            logger.info(f"✅ Assigned report sent to {name} ({phone})")
                            reports_sent += 1
                        else:
                            logger.error(f"❌ Failed to send assigned report to {name}: {result}")
                            errors += 1
            except Exception as e:
                logger.error(f"Error sending assigned report to {name}: {e}")
                errors += 1
    
    logger.info(f"📊 Daily reports complete: {reports_sent} sent, {errors} errors")
