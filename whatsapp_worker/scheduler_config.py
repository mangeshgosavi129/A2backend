"""
Scheduler Configuration for Deadline Reminders

Defines reminder intervals and scheduler settings.
"""

# Reminder intervals in minutes before deadline
REMINDER_60_MIN = 60    # Warning: "wrap it up"
REMINDER_10_MIN = 10    # Prompt: "tell me to mark complete"
REMINDER_OVERDUE = 0    # Past deadline notice

# How often the scheduler checks for tasks (in seconds)
SCHEDULER_CHECK_INTERVAL = 60  # Every 1 minute

# Daily summary report time (hour in 24h format, IST)
DAILY_REPORT_HOUR = 17   # 5 PM
DAILY_REPORT_MINUTE = 0
