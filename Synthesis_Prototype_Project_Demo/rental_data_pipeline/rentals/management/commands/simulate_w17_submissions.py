"""
simulate_w17_submissions.py

Simulates all vendors EXCEPT Brown Group having submitted their W17 data
for the Junior Super User to review.

  - Reads master_ledger_2026_W17.csv from docs/.
  - Creates RentalStaging rows (SUBMITTED) for every weekly vendor
    except Brown Group.
  - Monthly vendors (Christensen, Nixon and Davis; Davidson PLC; Lee-Jordan;
    Morales, Allen and Jones; Preston LLC; West Inc) already have carry-forward
    staging rows from seed_w17_open.py — no duplicates are created.
  - Marks corresponding W17 VendorAudit rows verified=True so the
    Junior Super User sees a "Submitted" status on the review dashboard.

Prerequisites:
    python manage.py seed_w17_open   (must run first)

Usage:
    python manage.py simulate_w17_submissions
    python manage.py simulate_w17_submissions --reset   # wipe & re-seed
"""

import csv
import datetime
import os
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from rentals.models import (
    RentalStaging,
    SubmissionStatus,
    UserProfile,
    VendorAudit,
)

User = get_user_model()

TARGET_YEAR = 2026
TARGET_WEEK = 17
MONDAY_W17  = datetime.date.fromisocalendar(TARGET_YEAR, TARGET_WEEK, 1)  # 2026-04-21

EXCLUDE_VENDOR = "Brown Group"

MONTHLY_VENDORS = {
    "Christensen, Nixon and Davis",
    "Davidson PLC",
    "Lee-Jordan",
    "Morales, Allen and Jones",
    "Preston LLC",
    "West Inc",
}

# Path from this file: commands/ → management/ → rentals/ → rental_data_pipeline/ → repo root → docs/
_HERE     = os.path.dirname(os.path.abspath(__file__))
CSV_PATH  = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "..", "docs", "master_ledger_2026_W17.csv")
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _parse_rate(raw: str) -> Decimal:
    """'$2,027.38' → Decimal('2027.38'), returns 0 on failure."""
    if not raw or raw.strip() in ("", "—"):
        return Decimal("0.00")
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0.00")


def _parse_date(raw: str):
    """'MM/DD/YYYY' → date object, or None for blank / '—'."""
    if not raw or raw.strip() in ("", "—"):
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _vendor_user(vendor_name: str):
    profile = (
        UserProfile.objects.select_related("user", "company")
        .filter(role="vendor", company__name=vendor_name)
        .first()
    )
    return profile.user if profile else None


# ── command ──────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Simulate W17 vendor submissions for Junior Super User review — "
        "all vendors except Brown Group."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously simulated staging rows before re-seeding.",
        )

    def handle(self, *args, **options):
        if not os.path.isfile(CSV_PATH):
            self.stderr.write(self.style.ERROR(f"CSV not found: {CSV_PATH}"))
            return

        admin_user = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.first()
        )

        with transaction.atomic():

            # ── optional reset ───────────────────────────────────────────────
            if options["reset"]:
                deleted, _ = RentalStaging.objects.filter(
                    cycle_year=TARGET_YEAR,
                    cycle_week=TARGET_WEEK,
                    source_file="simulate_w17_submissions",
                ).delete()
                self.stdout.write(f"Reset: {deleted} simulated staging rows removed.")

            # ── parse CSV, build staging rows ────────────────────────────────
            rows_to_create  = []
            vendors_seen    = set()
            skipped_exists  = 0
            skipped_monthly = 0

            with open(CSV_PATH, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    vendor = row.get("RENTAL CO.", "").strip()

                    if vendor == EXCLUDE_VENDOR:
                        continue                         # Brown Group — intentionally excluded

                    vendors_seen.add(vendor)

                    if vendor in MONTHLY_VENDORS:
                        skipped_monthly += 1
                        continue                         # already has carry-forward staging

                    equip_id = row.get("EQUIPMENT #", "").strip()

                    # idempotent: skip if staging row already exists
                    if RentalStaging.objects.filter(
                        vendor_name=vendor,
                        equipment_id=equip_id,
                        cycle_year=TARGET_YEAR,
                        cycle_week=TARGET_WEEK,
                    ).exists():
                        skipped_exists += 1
                        continue

                    sn_req   = row.get("SN REQ #", "").strip()
                    comments = row.get("COMMENTS", "").strip()
                    if sn_req   == "—": sn_req   = ""
                    if comments == "—": comments = ""

                    rent_start = _parse_date(row.get("RENT START", ""))
                    if rent_start is None:
                        rent_start = datetime.date.today()

                    rows_to_create.append(RentalStaging(
                        vendor_name          = vendor,
                        vendor_code          = "",
                        equipment_id         = equip_id,
                        equipment_description= row.get("DESCRIPTION", "").strip(),
                        equipment_category   = row.get("TYPE OF EQUIP.", "").strip(),
                        quantity             = 1,
                        rate_daily           = _parse_rate(row.get("MO. RATE $", "")),
                        currency             = "USD",
                        on_rent_start        = rent_start,
                        on_rent_end          = _parse_date(row.get("PROJ. END", "")),
                        po_number            = row.get("PO #", "").strip(),
                        sn_request_number    = sn_req,
                        comments             = comments,
                        cycle_week           = TARGET_WEEK,
                        cycle_year           = TARGET_YEAR,
                        source_file          = "simulate_w17_submissions",
                        submitted_by         = _vendor_user(vendor) or admin_user,
                        status               = SubmissionStatus.SUBMITTED,
                        is_validated         = True,
                        validation_errors    = "",
                    ))

            if rows_to_create:
                RentalStaging.objects.bulk_create(rows_to_create)

            # ── mark VendorAudit rows verified ───────────────────────────────
            now         = timezone.now()
            audit_updated = 0
            audit_skipped = 0

            for vendor_name in vendors_seen:
                audit = VendorAudit.objects.filter(
                    vendor_name=vendor_name,
                    cycle_date=MONDAY_W17,
                ).first()
                if not audit:
                    audit_skipped += 1
                    continue
                if not audit.verified:
                    audit.verified     = True
                    audit.submitted_at = audit.submitted_at or now
                    audit.is_late      = False
                    audit.save(update_fields=["verified", "submitted_at", "is_late"])
                    audit_updated += 1

        # ── summary ─────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ W{TARGET_WEEK} simulation complete ({MONDAY_W17}):"
        ))
        self.stdout.write(f"  Staging rows created    : {len(rows_to_create)}")
        self.stdout.write(f"  Skipped (already exist) : {skipped_exists}")
        self.stdout.write(f"  Skipped (monthly/carry) : {skipped_monthly}")
        self.stdout.write(f"  Audits marked verified  : {audit_updated}")
        self.stdout.write(f"  Audits without row      : {audit_skipped}")
        self.stdout.write(
            f"\n  Brown Group              : NOT submitted — awaiting review by Junior Super User"
        )
        self.stdout.write(
            f"  Junior Super User login  : junior_super_01"
        )
        self.stdout.write(
            f"  Review URL               : http://127.0.0.1:8000/review/"
        )
