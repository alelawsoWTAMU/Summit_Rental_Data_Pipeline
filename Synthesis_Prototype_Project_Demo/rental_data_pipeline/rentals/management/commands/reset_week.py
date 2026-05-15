"""
Management command: reset_week

Deletes the current week's published RentalMaster rows and resets all
VendorAudit records for that week back to unverified/pending.  Staging
rows are preserved so vendors can re-submit.

Usage:
    python manage.py reset_week              # resets the current ISO week
    python manage.py reset_week --week 18    # resets a specific week
    python manage.py reset_week --year 2026 --week 18
"""
import datetime

from django.core.management.base import BaseCommand

from rentals.models import RentalMaster, VendorAudit, VendorCompany


class Command(BaseCommand):
    help = "Delete published master rows for a week and reset vendor audits to pending."

    def add_arguments(self, parser):
        today = datetime.date.today()
        iso = today.isocalendar()
        parser.add_argument(
            "--week",
            type=int,
            default=iso[1],
            help=f"ISO week number to reset (default: current week {iso[1]}).",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=iso[0],
            help=f"ISO year (default: {iso[0]}).",
        )

    def handle(self, *args, **options):
        week = options["week"]
        year = options["year"]

        try:
            cycle_date = datetime.date.fromisocalendar(year, week, 1)
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(f"Invalid week/year: {exc}"))
            return

        self.stdout.write(
            f"Resetting Week {week}, {year} (cycle date: {cycle_date}) …"
        )

        # Delete published master rows for this week
        deleted, _ = RentalMaster.objects.filter(
            cycle_week=week, cycle_year=year
        ).delete()
        self.stdout.write(f"  Deleted {deleted} RentalMaster row(s).")

        # Reset VendorAudit records for this week back to unverified/pending
        updated = VendorAudit.objects.filter(cycle_date=cycle_date).update(
            verified=False,
            is_late=False,
            no_change=False,
            no_change_declared_at=None,
            submitted_at=None,
            notes="",
        )
        self.stdout.write(f"  Reset {updated} VendorAudit record(s) to pending.")

        # Correct cadence snapshot from VendorCompany in case rows were seeded
        # before the cadence fix was applied.
        cadence_map = {vc.name: vc.cadence for vc in VendorCompany.objects.all()}
        for audit in VendorAudit.objects.filter(cycle_date=cycle_date):
            expected = cadence_map.get(audit.vendor_name)
            if expected and audit.cadence != expected:
                audit.cadence = expected
                audit.save(update_fields=["cadence"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Week {week} ({year}) is now open for vendor submissions."
            )
        )
