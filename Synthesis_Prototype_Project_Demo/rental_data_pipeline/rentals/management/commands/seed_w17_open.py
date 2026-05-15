"""
seed_w17_open.py

Open Week 17 (2026-W17, Monday 2026-04-21) in the correct state:

  • Designates 6 vendors as monthly cadence (updates ALL their VendorAudit rows).
  • Creates W17 VendorAudit rows for all 25 vendors:
      – Weekly vendors  → verified=False, Pending (will submit Mon–Thu)
      – Monthly vendors → verified=True, no_change=True ("not required this week")
  • Carries W16 staging rows for monthly vendors into W17 staging so their
    equipment appears in the consolidated table immediately.
  • Does NOT create any W17 staging rows for weekly vendors — they will
    submit through the portal during the week.

Usage:
    python manage.py seed_w17_open
    python manage.py seed_w17_open --reset   # wipe W17 state and re-seed
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from rentals.models import (
    RentalStaging,
    SubmissionStatus,
    UserProfile,
    VendorAudit,
    VendorCompany,
)

User = get_user_model()

TARGET_YEAR  = 2026
TARGET_WEEK  = 17
MONDAY_W17   = datetime.date.fromisocalendar(TARGET_YEAR, TARGET_WEEK, 1)  # 2026-04-21

SOURCE_YEAR  = 2026
SOURCE_WEEK  = 16

# Vendors designated as monthly reporters — they submit once per month,
# not every week. Their W16 data carries forward automatically.
MONTHLY_VENDORS = {
    "Christensen, Nixon and Davis",
    "Davidson PLC",
    "Lee-Jordan",
    "Morales, Allen and Jones",
    "Preston LLC",
    "West Inc",
}


class Command(BaseCommand):
    help = "Open Week 17 cycle: set cadences, create audit rows, carry monthly vendor data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing W17 audit and staging rows before seeding.",
        )

    def handle(self, *args, **options):
        approver = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.first()
        )

        all_companies = list(VendorCompany.objects.filter(is_active=True).order_by("name"))
        if not all_companies:
            self.stderr.write(self.style.ERROR("No active VendorCompany records found."))
            return

        all_names = [c.name for c in all_companies]

        with transaction.atomic():
            if options["reset"]:
                da, _ = VendorAudit.objects.filter(cycle_date=MONDAY_W17).delete()
                ds, _ = RentalStaging.objects.filter(
                    cycle_year=TARGET_YEAR, cycle_week=TARGET_WEEK
                ).delete()
                self.stdout.write(f"Reset: {da} audit rows, {ds} staging rows deleted for W{TARGET_WEEK}.")

            # ── 1. Update cadence on ALL existing VendorAudit rows ───────────
            updated_monthly = VendorAudit.objects.filter(
                vendor_name__in=MONTHLY_VENDORS
            ).update(cadence="monthly")
            updated_weekly  = VendorAudit.objects.filter(
                vendor_name__in=[n for n in all_names if n not in MONTHLY_VENDORS]
            ).update(cadence="weekly")
            self.stdout.write(
                f"Cadence updated — monthly: {updated_monthly} rows, weekly: {updated_weekly} rows."
            )

            # ── 2. Create W17 VendorAudit rows ───────────────────────────────
            created_audit = 0
            skipped_audit = 0
            for name in all_names:
                is_monthly = name in MONTHLY_VENDORS
                vendor_user = self._find_vendor_user(name)
                obj, was_created = VendorAudit.objects.get_or_create(
                    vendor_name=name,
                    cycle_date=MONDAY_W17,
                    defaults={
                        "vendor_user":  vendor_user,
                        "cadence":      "monthly" if is_monthly else "weekly",
                        "verified":     is_monthly,     # monthly = auto-verified
                        "no_change":    is_monthly,     # monthly = not required this week
                        "is_late":      False,
                        "submitted_at": timezone.now() if is_monthly else None,
                        "notes": (
                            "Monthly vendor — weekly submission not required."
                            if is_monthly
                            else ""
                        ),
                    },
                )
                if was_created:
                    created_audit += 1
                else:
                    skipped_audit += 1

            self.stdout.write(
                f"W{TARGET_WEEK} audit rows — created: {created_audit}, already existed: {skipped_audit}."
            )

            # ── 3. Carry W16 staging rows for monthly vendors into W17 ───────
            w16_monthly_rows = list(
                RentalStaging.objects.filter(
                    cycle_year=SOURCE_YEAR,
                    cycle_week=SOURCE_WEEK,
                    vendor_name__in=MONTHLY_VENDORS,
                )
            )
            if not w16_monthly_rows:
                self.stdout.write(self.style.WARNING(
                    f"No W{SOURCE_WEEK} staging rows found for monthly vendors — "
                    "run seed_w16 first if this is unexpected."
                ))
            else:
                # Skip if W17 staging already has rows for these vendors
                existing_w17_monthly = RentalStaging.objects.filter(
                    cycle_year=TARGET_YEAR,
                    cycle_week=TARGET_WEEK,
                    vendor_name__in=MONTHLY_VENDORS,
                ).exists()

                if existing_w17_monthly and not options["reset"]:
                    self.stdout.write(self.style.WARNING(
                        "W17 monthly vendor staging rows already exist — skipping carry-forward. "
                        "Use --reset to overwrite."
                    ))
                else:
                    carry_objs = []
                    for src in w16_monthly_rows:
                        carry_objs.append(RentalStaging(
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
                            comments=src.comments,
                            cycle_week=TARGET_WEEK,
                            cycle_year=TARGET_YEAR,
                            source_file=f"carry_forward_w{SOURCE_WEEK}_{SOURCE_YEAR}",
                            submitted_by=src.submitted_by,
                            status=SubmissionStatus.SUBMITTED,
                            is_validated=True,
                            validation_errors="",
                        ))
                    RentalStaging.objects.bulk_create(carry_objs)
                    self.stdout.write(
                        f"Carried {len(carry_objs)} monthly vendor rows from W{SOURCE_WEEK} into W{TARGET_WEEK} staging."
                    )

        # Summary
        weekly_count  = len([n for n in all_names if n not in MONTHLY_VENDORS])
        monthly_count = len([n for n in all_names if n in MONTHLY_VENDORS])
        self.stdout.write(self.style.SUCCESS(f"\n✓ W{TARGET_WEEK} cycle opened ({MONDAY_W17}):"))
        self.stdout.write(f"  Weekly vendors (Pending):       {weekly_count}")
        self.stdout.write(f"  Monthly vendors (Not Required): {monthly_count}")
        self.stdout.write(f"  Monthly staging rows carried:   {len(w16_monthly_rows) if w16_monthly_rows else 0}")

    def _find_vendor_user(self, vendor_name):
        profile = (
            UserProfile.objects.select_related("user", "company")
            .filter(role="vendor", company__name=vendor_name)
            .first()
        )
        return profile.user if profile else None
