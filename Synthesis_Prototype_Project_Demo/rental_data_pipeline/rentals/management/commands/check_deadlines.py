"""
Management command: check_deadlines

Scans vendor_audit for unverified vendors past the weekly or monthly
submission cutoff and sends an SMTP nudge email to each late vendor.
The Super User is CC'd on every nudge.

Weekly cutoff:  Thursday 14:00 CST  (UTC-6 standard / UTC-5 daylight)
Monthly cutoff: Last calendar day of the month at 14:00 CST

Usage:
    python manage.py check_deadlines
    python manage.py check_deadlines --dry-run
    python manage.py check_deadlines --cycle-date 2026-05-15

Environment variables required (never hardcode credentials):
    EMAIL_HOST          SMTP host, e.g. smtp.office365.com
    EMAIL_PORT          SMTP port, e.g. 587
    EMAIL_HOST_USER     Sender address
    EMAIL_HOST_PASSWORD Sender password / app password
    EMAIL_USE_TLS       "true" or "false" (default true)
    SUPERUSER_CC_EMAIL  Email address to CC on every nudge
"""

import os
from datetime import date, datetime, time, timedelta

import pytz
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from rentals.models import VendorAudit, SubmissionCadence

User = get_user_model()

CST = pytz.timezone("America/Chicago")
WEEKLY_CUTOFF_WEEKDAY = 3   # Thursday (0=Monday)
CUTOFF_HOUR = 14            # 14:00 CST


def _weekly_cutoff_for(cycle_date: date) -> datetime:
    """Return the aware Thursday 14:00 CST deadline for the week containing cycle_date."""
    days_to_thursday = (WEEKLY_CUTOFF_WEEKDAY - cycle_date.weekday()) % 7
    thursday = cycle_date + timedelta(days=days_to_thursday)
    naive_cutoff = datetime.combine(thursday, time(CUTOFF_HOUR, 0, 0))
    return CST.localize(naive_cutoff)


def _monthly_cutoff_for(cycle_date: date) -> datetime:
    """Return the aware last-day-of-month 14:00 CST deadline for cycle_date's month."""
    if cycle_date.month == 12:
        last_day = date(cycle_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(cycle_date.year, cycle_date.month + 1, 1) - timedelta(days=1)
    naive_cutoff = datetime.combine(last_day, time(CUTOFF_HOUR, 0, 0))
    return CST.localize(naive_cutoff)


def _is_past_cutoff(audit: VendorAudit, now_aware: datetime) -> bool:
    if audit.cadence == SubmissionCadence.WEEKLY:
        cutoff = _weekly_cutoff_for(audit.cycle_date)
    else:
        cutoff = _monthly_cutoff_for(audit.cycle_date)
    return now_aware >= cutoff


class Command(BaseCommand):
    help = (
        "Check vendor_audit for unverified vendors past their submission deadline "
        "and send SMTP nudge emails with the Super User CC'd."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List late vendors without sending any emails.",
        )
        parser.add_argument(
            "--cycle-date",
            type=str,
            default=None,
            help="Only check audit records for this cycle date (YYYY-MM-DD). "
                 "Defaults to all open cycles.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        cycle_date_filter: str | None = options["cycle_date"]

        now_aware = timezone.now().astimezone(CST)

        # --- email config from environment ---
        smtp_host = os.environ.get("EMAIL_HOST", "")
        smtp_port = int(os.environ.get("EMAIL_PORT", "587"))
        smtp_user = os.environ.get("EMAIL_HOST_USER", "")
        smtp_password = os.environ.get("EMAIL_HOST_PASSWORD", "")
        use_tls = os.environ.get("EMAIL_USE_TLS", "true").lower() != "false"
        cc_email = os.environ.get("SUPERUSER_CC_EMAIL", "")

        if not dry_run and not smtp_host:
            self.stderr.write(
                self.style.ERROR(
                    "EMAIL_HOST environment variable is not set. "
                    "Run with --dry-run or set email env vars."
                )
            )
            return

        # --- query ---
        qs = VendorAudit.objects.filter(verified=False)
        if cycle_date_filter:
            try:
                parsed_date = date.fromisoformat(cycle_date_filter)
                qs = qs.filter(cycle_date=parsed_date)
            except ValueError:
                self.stderr.write(
                    self.style.ERROR(f"Invalid date format: {cycle_date_filter}. Use YYYY-MM-DD.")
                )
                return

        late_audits = [a for a in qs if _is_past_cutoff(a, now_aware)]

        if not late_audits:
            self.stdout.write(self.style.SUCCESS("No overdue vendors found."))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {len(late_audits)} overdue vendor cycle(s):")
        )

        sent = 0
        errors = 0

        for audit in late_audits:
            vendor_email = self._resolve_vendor_email(audit)
            cadence_label = audit.get_cadence_display()

            if audit.cadence == SubmissionCadence.WEEKLY:
                cutoff_dt = _weekly_cutoff_for(audit.cycle_date)
                deadline_str = cutoff_dt.strftime("%A, %B %-d at %-I:%M %p CST")
            else:
                cutoff_dt = _monthly_cutoff_for(audit.cycle_date)
                deadline_str = cutoff_dt.strftime("%B %-d at %-I:%M %p CST")

            subject = (
                f"[Action Required] {cadence_label} Rental Data Submission Overdue "
                f"\u2014 {audit.vendor_name}"
            )
            body = (
                f"Dear {audit.vendor_name},\n\n"
                f"Your {cadence_label.lower()} equipment rental data submission for the "
                f"cycle ending {audit.cycle_date} was due by {deadline_str} and has not "
                f"been received.\n\n"
                f"Please log in to the Vendor Portal and either:\n"
                f"  \u2022  Update your equipment records and submit, or\n"
                f"  \u2022  Declare 'No Changes this week' if your inventory is unchanged.\n\n"
                f"Failure to submit may delay the weekly data refresh and approval cycle.\n\n"
                f"If you believe this notice is in error, please contact the operations team.\n\n"
                f"--- Vendor Portal Automated Notice ---"
            )

            self.stdout.write(
                f"  {'[DRY RUN] ' if dry_run else ''}"
                f"Nudge \u2192 {audit.vendor_name} "
                f"({vendor_email or 'no email'}) | cycle {audit.cycle_date} | {cadence_label}"
            )

            if dry_run or not vendor_email:
                continue

            try:
                cc_list = [cc_email] if cc_email else []
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=smtp_user,
                    recipient_list=[vendor_email],
                    fail_silently=False,
                )
                # Django's send_mail doesn't support CC natively; resend with headers if CC set
                if cc_list:
                    from django.core.mail import EmailMessage
                    email_msg = EmailMessage(
                        subject=subject,
                        body=body,
                        from_email=smtp_user,
                        to=[vendor_email],
                        cc=cc_list,
                    )
                    email_msg.send(fail_silently=False)

                # Mark as late in the audit record
                audit.is_late = True
                audit.save(update_fields=["is_late"])
                sent += 1
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f"    Failed to send to {vendor_email}: {exc}")
                )
                errors += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete. {len(late_audits)} overdue vendor(s) identified. "
                    f"No emails sent."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Sent: {sent}  Errors: {errors}  "
                    f"Skipped (no email): {len(late_audits) - sent - errors}"
                )
            )

    @staticmethod
    def _resolve_vendor_email(audit: VendorAudit) -> str | None:
        """Return the email address for the vendor user linked to this audit record."""
        if audit.vendor_user_id and audit.vendor_user.email:
            return audit.vendor_user.email
        # Fall back: look for any active vendor user for this company name
        try:
            from rentals.models import UserProfile
            profile = (
                UserProfile.objects
                .select_related("user", "company")
                .filter(company__name=audit.vendor_name, role="vendor")
                .first()
            )
            return profile.user.email if profile and profile.user.email else None
        except Exception:
            return None
