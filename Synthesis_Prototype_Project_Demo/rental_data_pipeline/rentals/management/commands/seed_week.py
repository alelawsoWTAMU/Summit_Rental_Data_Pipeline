"""
seed_week.py

Clone an existing cycle week's staging rows into a new cycle week,
simulating all vendors turning in their weekly rental data.

Usage:
    python manage.py seed_week --from-week 15 --to-week 16 --year 2026
    python manage.py seed_week --from-week 15 --to-week 16 --year 2026 --reset
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from rentals.models import RentalStaging, SubmissionStatus, VendorAudit


class Command(BaseCommand):
    help = "Clone staging rows from one cycle week into a new cycle week."

    def add_arguments(self, parser):
        parser.add_argument("--from-week", type=int, required=True, help="Source cycle week number.")
        parser.add_argument("--to-week",   type=int, required=True, help="Target cycle week number.")
        parser.add_argument("--year",      type=int, required=True, help="ISO year for both weeks.")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete any existing staging rows for the target week before seeding.",
        )

    def handle(self, *args, **options):
        from_week = options["from_week"]
        to_week   = options["to_week"]
        year      = options["year"]
        do_reset  = options["reset"]

        source_rows = list(
            RentalStaging.objects.filter(cycle_week=from_week, cycle_year=year)
        )

        if not source_rows:
            self.stderr.write(
                self.style.ERROR(f"No staging rows found for Week {from_week}, {year}.")
            )
            return

        if do_reset:
            deleted, _ = RentalStaging.objects.filter(
                cycle_week=to_week, cycle_year=year
            ).delete()
            self.stdout.write(f"Deleted {deleted} existing rows for Week {to_week}.")

        # Monday of the target week
        target_monday = datetime.date.fromisocalendar(year, to_week, 1)
        source_monday = datetime.date.fromisocalendar(year, from_week, 1)
        date_delta    = target_monday - source_monday  # 7 days forward

        now = timezone.now()
        new_rows = []
        for src in source_rows:
            new = RentalStaging(
                vendor_name=src.vendor_name,
                vendor_code=src.vendor_code,
                equipment_id=src.equipment_id,
                equipment_description=src.equipment_description,
                quantity=src.quantity,
                rate_daily=src.rate_daily,
                currency=src.currency,
                on_rent_start=src.on_rent_start,
                on_rent_end=src.on_rent_end,
                po_number=src.po_number,
                sn_request_number=src.sn_request_number,
                cycle_week=to_week,
                cycle_year=year,
                source_file=f"week{to_week}_{year}_vendor_submission",
                submitted_by=src.submitted_by,
                status=SubmissionStatus.SUBMITTED,
                is_validated=True,
                validation_errors="",
            )
            new_rows.append(new)

        created = RentalStaging.objects.bulk_create(new_rows)

        # Upsert VendorAudit rows so the review page shows them as submitted
        target_cycle_date = target_monday
        vendors_seen = set()
        for row in source_rows:
            if row.vendor_name in vendors_seen:
                continue
            vendors_seen.add(row.vendor_name)
            VendorAudit.objects.update_or_create(
                vendor_name=row.vendor_name,
                cycle_date=target_cycle_date,
                defaults={
                    "verified":     True,
                    "is_late":      False,
                    "notes":        f"Submitted Week {to_week} data.",
                    "submitted_at": now,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(created)} staging rows for Week {to_week}, {year}."
        ))
        self.stdout.write(
            f"Upserted {len(vendors_seen)} VendorAudit entries for cycle {target_cycle_date}."
        )
