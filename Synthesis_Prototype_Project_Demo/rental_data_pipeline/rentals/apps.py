import os
import sys

from django.apps import AppConfig


class RentalsConfig(AppConfig):
    name = 'rentals'

    def ready(self):
        # Don't run the scheduler during migrations, shell commands, or tests.
        # Only start it when the actual web server process is running.
        if 'runserver' not in sys.argv:
            return
        # Avoid double-start in Django's auto-reloader (reloader spawns a child
        # process with RUN_MAIN=true; only the child should run the scheduler).
        if os.environ.get('RUN_MAIN') != 'true':
            return

        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        import pytz

        def _send_reminders():
            """Called automatically every Thursday at 14:00 CST by APScheduler."""
            from django.core.management import call_command
            call_command('send_vendor_reminders', force=True)

        cst = pytz.timezone('America/Chicago')
        scheduler = BackgroundScheduler(timezone=cst)
        # Every Thursday at 14:00 CST
        scheduler.add_job(
            _send_reminders,
            trigger=CronTrigger(day_of_week='thu', hour=14, minute=0, timezone=cst),
            id='vendor_reminders',
            replace_existing=True,
        )
        scheduler.start()
