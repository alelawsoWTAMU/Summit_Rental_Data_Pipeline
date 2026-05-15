"""
seed_history.py

Generate a believable 15-week rental history (weeks 1–14, 2026) derived from
the week-15 snapshot already in the database, then publish everything to
RentalMaster.

Strategy per week:
  - Start from week-15 roster as the "ground truth" equipment pool.
  - Each earlier week, some equipment hasn't been added yet (probability grows
    the further back we go) and a handful of active items may have been
    off-rent (end-date already passed by that week's Monday).
  - 2–5% of rows get a small random rate drift (±3%) to simulate invoice
    corrections.
  - 1–2 vendors per week are marked as "late" to build a realistic compliance
    history.
  - Everything is published straight into RentalMaster so charts have data.

Usage:
    python manage.py seed_history               # weeks 1-14
    python manage.py seed_history --reset       # clear first, then seed
    python manage.py seed_history --weeks 1-10  # custom range
"""

import datetime
import random
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from rentals.models import RentalMaster, RentalStaging, SubmissionStatus, VendorAudit

User = get_user_model()

SEED = 42  # reproducible randomness


class Command(BaseCommand):
    help = "Seed weeks 1–14 of 2026 with believable history derived from week 15."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete staging and master rows for weeks 1-14 before seeding.",
        )
        parser.add_argument(
            "--weeks",
            type=str,
            default="1-14",
            help="Week range to generate, e.g. '1-14' or '1-10'.",
        )

    def handle(self, *args, **options):
        rng = random.Random(SEED)

        # Parse week range
        try:
            parts = options["weeks"].split("-")
            week_start, week_end = int(parts[0]), int(parts[1])
        except Exception:
            self.stderr.write("Invalid --weeks format. Use e.g. '1-14'.")
            return

        year = 2026

        # Grab the week-15 snapshot as the reference pool
        pool = list(
            RentalStaging.objects.filter(cycle_week=15, cycle_year=year)
            .values(
                "vendor_name", "vendor_code", "equipment_id",
                "equipment_description", "quantity", "rate_daily",
                "currency", "on_rent_start", "on_rent_end",
                "po_number", "sn_request_number", "submitted_by_id",
            )
        )
        if not pool:
            self.stderr.write("No week-15 data found. Run seed_rental_data first.")
            return

        # Find an admin user to act as approver
        approver = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.first()
        )

        # Distinct vendor names
        all_vendors = sorted({r["vendor_name"] for r in pool})
        # Pick 2-3 vendors that will occasionally be late throughout history
        chronic_late = rng.sample(all_vendors, k=min(3, len(all_vendors)))

        if options["reset"]:
            deleted_s, _ = RentalStaging.objects.filter(
                cycle_year=year, cycle_week__gte=week_start, cycle_week__lte=week_end
            ).delete()
            deleted_m, _ = RentalMaster.objects.filter(
                cycle_year=year, cycle_week__gte=week_start, cycle_week__lte=week_end
            ).delete()
            deleted_a, _ = VendorAudit.objects.filter(
                cycle_date__gte=datetime.date.fromisocalendar(year, week_start, 1),
                cycle_date__lte=datetime.date.fromisocalendar(year, week_end, 1),
            ).delete()
            self.stdout.write(
                f"Cleared: {deleted_s} staging, {deleted_m} master, {deleted_a} audit rows."
            )

        total_staging = 0
        total_master  = 0

        with transaction.atomic():
            for week in range(week_start, week_end + 1):
                monday = datetime.date.fromisocalendar(year, week, 1)
                week_rows = self._build_week(pool, week, year, monday, rng)

                # How many vendors are late this week (0-2)
                n_late = rng.randint(0, 2)
                late_vendors = set(rng.sample(chronic_late, k=min(n_late, len(chronic_late))))

                # --- Staging ---
                staging_objs = []
                for r in week_rows:
                    staging_objs.append(RentalStaging(
                        vendor_name=r["vendor_name"],
                        vendor_code=r["vendor_code"],
                        equipment_id=r["equipment_id"],
                        equipment_description=r["equipment_description"],
                        quantity=r["quantity"],
                        rate_daily=r["rate_daily"],
                        currency=r["currency"],
                        on_rent_start=r["on_rent_start"],
                        on_rent_end=r["on_rent_end"],
                        po_number=r["po_number"],
                        sn_request_number=r["sn_request_number"],
                        cycle_week=week,
                        cycle_year=year,
                        source_file=f"history_seed_wk{week}_{year}",
                        submitted_by_id=r["submitted_by_id"],
                        status=SubmissionStatus.APPROVED,
                        is_validated=True,
                        validation_errors="",
                    ))
                created_staging = RentalStaging.objects.bulk_create(staging_objs)
                total_staging += len(created_staging)

                # --- Master ---
                master_objs = []
                for s in created_staging:
                    master_objs.append(RentalMaster(
                        vendor_name=s.vendor_name,
                        vendor_code=s.vendor_code,
                        equipment_id=s.equipment_id,
                        equipment_description=s.equipment_description,
                        quantity=s.quantity,
                        rate_daily=s.rate_daily,
                        currency=s.currency,
                        on_rent_start=s.on_rent_start,
                        on_rent_end=s.on_rent_end,
                        po_number=s.po_number,
                        sn_request_number=s.sn_request_number,
                        cycle_week=week,
                        cycle_year=year,
                        source_file=s.source_file,
                        approved_from=s,
                        approved_by=approver,
                        is_active=True,
                    ))
                RentalMaster.objects.bulk_create(master_objs)
                total_master += len(master_objs)

                # --- VendorAudit ---
                vendors_in_week = {r["vendor_name"] for r in week_rows}
                # A few vendors who had no equipment that week are still audited as pending
                for vendor in all_vendors:
                    is_late = vendor in late_vendors
                    submitted = monday + datetime.timedelta(days=rng.randint(0, 4))
                    VendorAudit.objects.update_or_create(
                        vendor_name=vendor,
                        cycle_date=monday,
                        defaults={
                            "verified":     not is_late,
                            "is_late":      is_late,
                            "submitted_at": timezone.make_aware(
                                datetime.datetime.combine(submitted, datetime.time(
                                    rng.randint(7, 17), rng.randint(0, 59)
                                ))
                            ) if not is_late else None,
                            "notes": (
                                "Late submission — follow-up required." if is_late
                                else f"Week {week} data submitted on time."
                            ),
                        },
                    )

                self.stdout.write(
                    f"  Week {week:>2}: {len(week_rows):>4} rows  "
                    f"({len(late_vendors)} late vendor{'s' if len(late_vendors) != 1 else ''})"
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {total_staging} staging, {total_master} master rows created "
            f"for weeks {week_start}–{week_end}, {year}."
        ))

    # ------------------------------------------------------------------ #

    def _build_week(self, pool, week, year, monday, rng):
        """
        Derive a plausible equipment list for `week` from the week-15 pool.

        Rules:
          - Equipment whose on_rent_start > monday is excluded (not yet rented).
          - Equipment whose on_rent_end < monday – 14 days is excluded (well finished).
          - Each remaining row has a (week/15 * 4)% chance of being temporarily
            off-rent that week (returned and not yet replaced).
          - 3% of included rows get a rate drift of ±2%.
        """
        rows = []
        dropout_chance = min(0.18, (15 - week) * 0.012)  # more dropout in earlier weeks

        for r in pool:
            start = r["on_rent_start"]
            end   = r["on_rent_end"]

            # Not yet on rent this week
            if start and start > monday:
                continue

            # Clearly finished well before this week
            if end and end < (monday - datetime.timedelta(days=14)):
                continue

            # Simulate occasional temporary off-rent in earlier weeks
            if rng.random() < dropout_chance:
                continue

            # Copy the row, possibly adjusting the rate slightly
            rate = r["rate_daily"]
            if rng.random() < 0.03:
                factor = Decimal(str(round(rng.uniform(0.98, 1.02), 4)))
                rate = (rate * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            rows.append({**r, "rate_daily": rate})

        return rows
