"""
Management command: send_vendor_reminders

Sends a reminder email to every weekly vendor who has NOT yet submitted
(verified=False, no_change=False) for the current open cycle.

Intended to run automatically at 14:00 CST every Thursday via Task Scheduler
or cron, but can also be triggered manually at any time.

Usage:
    python manage.py send_vendor_reminders
    python manage.py send_vendor_reminders --dry-run
    python manage.py send_vendor_reminders --force   # skip Thursday/time check

Environment variables required:
    EMAIL_HOST          SMTP host
    EMAIL_PORT          SMTP port  (default 587)
    EMAIL_HOST_USER     Sender address
    EMAIL_HOST_PASSWORD Sender password / app password
    EMAIL_USE_TLS       "true" or "false" (default true)
    SUPERUSER_CC_EMAIL  (optional) address CC'd on every reminder
"""

import os
from datetime import date, datetime, time, timedelta

import pytz
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand

from rentals.models import UserProfile, VendorAudit, SubmissionCadence

CST = pytz.timezone("America/Chicago")
THURSDAY = 3          # Monday=0 … Sunday=6
CUTOFF_HOUR = 14      # 14:00 CST


def _current_thursday_cycle_date() -> date:
    """Return the Monday that opens the current week (matches VendorAudit cycle_date anchor)."""
    today = date.today()
    # Walk back to the most recent Monday (weekday() == 0 on Monday)
    return today - timedelta(days=today.weekday())


class Command(BaseCommand):
    help = (
        "Send 2 PM Thursday reminder emails to weekly vendors who have not yet "
        "submitted or declared no-change for the current cycle."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List vendors who would be emailed without actually sending.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip the Thursday / 14:00 CST guard and send regardless of when this runs.",
        )
        parser.add_argument(
            "--cycle-date",
            type=str,
            default=None,
            help="Override the cycle date to check (YYYY-MM-DD). Defaults to current week.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        force: bool = options["force"]
        cycle_date_arg: str | None = options["cycle_date"]

        now_cst: datetime = datetime.now(tz=CST)

        # ── Thursday / time guard ────────────────────────────────────────────
        if not force:
            if now_cst.weekday() != THURSDAY:
                self.stdout.write(
                    self.style.WARNING(
                        f"Today is not Thursday (weekday={now_cst.weekday()}). "
                        "Use --force to send anyway."
                    )
                )
                return
            if now_cst.hour < CUTOFF_HOUR:
                self.stdout.write(
                    self.style.WARNING(
                        f"Not yet 2:00 PM CST (current: {now_cst.strftime('%H:%M')} CST). "
                        "Use --force to send anyway."
                    )
                )
                return

        # ── Resolve cycle date ───────────────────────────────────────────────
        if cycle_date_arg:
            try:
                cycle_date = date.fromisoformat(cycle_date_arg)
            except ValueError:
                self.stderr.write(
                    self.style.ERROR(f"Invalid date: {cycle_date_arg}. Use YYYY-MM-DD.")
                )
                return
        else:
            cycle_date = _current_thursday_cycle_date()

        self.stdout.write(f"Checking cycle date: {cycle_date}")

        # ── Find unsubmitted weekly vendors for this cycle ───────────────────
        pending_audits = list(
            VendorAudit.objects.filter(
                cadence=SubmissionCadence.WEEKLY,
                cycle_date=cycle_date,
                verified=False,
                no_change=False,
            ).order_by("vendor_name")
        )

        if not pending_audits:
            self.stdout.write(
                self.style.SUCCESS(
                    f"All weekly vendors have submitted for cycle {cycle_date}. "
                    "No reminders needed."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(pending_audits)} vendor(s) pending submission:"
            )
        )

        # ── Email config ─────────────────────────────────────────────────────
        smtp_host = os.environ.get("EMAIL_HOST", "")
        smtp_user = os.environ.get("EMAIL_HOST_USER", "")
        cc_email = os.environ.get("SUPERUSER_CC_EMAIL", "")

        if not dry_run and not smtp_host:
            self.stderr.write(
                self.style.ERROR(
                    "EMAIL_HOST is not set. Run with --dry-run or configure email env vars."
                )
            )
            return

        # ── Deadline string for email body ───────────────────────────────────
        thursday = now_cst.date() if now_cst.weekday() == THURSDAY else (
            date.today() + timedelta(days=(THURSDAY - date.today().weekday()) % 7)
        )
        deadline_str = f"Thursday, {thursday.strftime('%B')} {thursday.day}, {thursday.year} at 2:00 PM CST"

        sent = 0
        skipped = 0
        errors = 0

        for audit in pending_audits:
            vendor_email = self._resolve_email(audit)

            self.stdout.write(
                f"  {'[DRY RUN] ' if dry_run else ''}"
                f"{audit.vendor_name} -> {vendor_email or 'NO EMAIL ON FILE'}"
            )

            if dry_run:
                continue

            if not vendor_email:
                skipped += 1
                continue

            subject = f"[Reminder] Weekly Rental Submission Due Today — {audit.vendor_name}"
            body = (
                f"Dear {audit.vendor_name},\n\n"
                f"This is a friendly reminder that your weekly equipment rental data "
                f"submission is due by {deadline_str}.\n\n"
                f"We have not yet received your submission for the current week "
                f"(cycle date: {cycle_date}).\n\n"
                f"Please log in to the Vendor Portal and either:\n"
                f"  - Update your equipment records and click 'Submit Weekly Report', or\n"
                f"  - Click 'No Changes This Week' if your inventory is unchanged.\n\n"
                f"If you have any questions, please reach out to the operations team.\n\n"
                f"--- Rental Data Pipeline Automated Reminder ---"
            )

            try:
                recipients = [vendor_email]
                cc_list = [cc_email] if cc_email else []
                msg = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=smtp_user,
                    to=recipients,
                    cc=cc_list,
                )
                msg.send(fail_silently=False)
                sent += 1
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f"    Failed to send to {vendor_email}: {exc}")
                )
                errors += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete. {len(pending_audits)} vendor(s) would be reminded."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Sent: {sent}  Skipped (no email): {skipped}  Errors: {errors}"
                )
            )

    @staticmethod
    def _resolve_email(audit: VendorAudit) -> str | None:
        """Return the vendor's email — from audit.vendor_user first, then profile lookup."""
        if audit.vendor_user_id and audit.vendor_user.email:
            return audit.vendor_user.email
        try:
            profile = (
                UserProfile.objects
                .select_related("user", "company")
                .filter(company__name=audit.vendor_name, role="vendor")
                .first()
            )
            return profile.user.email if profile and profile.user.email else None
        except Exception:
            return None
