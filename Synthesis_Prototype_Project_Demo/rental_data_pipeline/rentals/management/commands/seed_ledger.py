"""
seed_ledger.py

Replace weeks 1–17 of 2026 in RentalStaging, RentalMaster, and VendorAudit
with the actual data from master_ledger_linked_v4.csv.

  • Weeks 1–16  → APPROVED in staging, published to master, VendorAudit verified.
  • Week 17     → APPROVED in staging, published to master, VendorAudit verified.
  • All existing rows for weeks 1–17 are wiped before seeding (always reset).

Usage:
    python manage.py seed_ledger
    python manage.py seed_ledger --csv /path/to/other.csv
"""

import csv
import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from rentals.models import (
    RentalMaster,
    RentalStaging,
    SubmissionStatus,
    VendorAudit,
)

User = get_user_model()

TARGET_YEAR = 2026
WEEK_MIN    = 1
WEEK_MAX    = 17


class Command(BaseCommand):
    help = "Seed weeks 1–17 of 2026 from master_ledger_linked_v4.csv (always replaces existing data)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=str(
                Path(settings.BASE_DIR) / "docs" / "master_ledger_linked_v4.csv"
            ),
            help="Path to the master ledger CSV (default: docs/master_ledger_linked_v4.csv).",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"]).resolve()

        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        self.stdout.write(f"Reading {csv_path.name} …")
        rows = self._read_csv(csv_path)
        if not rows:
            raise CommandError("CSV has no data rows.")
        self.stdout.write(f"  {len(rows)} rows loaded.")

        approver = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if approver is None:
            raise CommandError(
                "No users found. Run seed_user_schema first to create users."
            )

        with transaction.atomic():
            # ── Wipe existing weeks 1–17 ────────────────────────────────────
            del_s, _ = RentalStaging.objects.filter(
                cycle_year=TARGET_YEAR,
                cycle_week__gte=WEEK_MIN,
                cycle_week__lte=WEEK_MAX,
            ).delete()
            del_m, _ = RentalMaster.objects.filter(
                cycle_year=TARGET_YEAR,
                cycle_week__gte=WEEK_MIN,
                cycle_week__lte=WEEK_MAX,
            ).delete()
            del_a, _ = VendorAudit.objects.filter(
                cycle_date__range=(
                    datetime.date.fromisocalendar(TARGET_YEAR, WEEK_MIN, 1),
                    datetime.date.fromisocalendar(TARGET_YEAR, WEEK_MAX, 1),
                )
            ).delete()
            self.stdout.write(
                f"Cleared: {del_s} staging, {del_m} master, {del_a} audit rows."
            )

            # ── Group CSV rows by week ───────────────────────────────────────
            by_week: dict[int, list[dict]] = {}
            skipped = 0
            for row in rows:
                week = self._parse_int(row.get("WK #"))
                year = self._parse_int(row.get("YEAR"))
                if week is None or year != TARGET_YEAR or not (WEEK_MIN <= week <= WEEK_MAX):
                    skipped += 1
                    continue
                by_week.setdefault(week, []).append(row)

            if skipped:
                self.stdout.write(f"  Skipped {skipped} out-of-range rows.")

            # ── Seed each week ───────────────────────────────────────────────
            total_staging = 0
            total_master  = 0
            total_audit   = 0

            for week in range(WEEK_MIN, WEEK_MAX + 1):
                week_rows = by_week.get(week, [])
                monday    = datetime.date.fromisocalendar(TARGET_YEAR, week, 1)

                # ── Build staging objects ────────────────────────────────────
                staging_objs = []
                for row in week_rows:
                    vendor_name = (row.get("RENTAL CO.") or "").strip()
                    if not vendor_name:
                        continue

                    equipment_id          = (row.get("EQUIPMENT #") or "UNKNOWN").strip()
                    equipment_description = (row.get("DESCRIPTION") or "Unknown").strip()
                    type_of_equip         = (row.get("TYPE OF EQUIP.") or "").strip()
                    on_rent_start         = self._parse_date(row.get("RENT START"))
                    on_rent_end           = self._parse_date(row.get("PROJ. END"))
                    rate                  = self._parse_decimal(row.get("MO. RATE $") or "0")
                    po_number             = (row.get("PO #") or "").strip()
                    sn_request            = (row.get("SN REQ #") or "").strip()
                    comments              = (row.get("COMMENTS") or "").strip()
                    published_by          = (row.get("PUBLISHED BY") or "").strip()

                    submitted_by = self._find_user(published_by)

                    validation_errors = []
                    if on_rent_start is None:
                        validation_errors.append("Invalid RENT START")
                    if rate is None:
                        validation_errors.append("Invalid MO. RATE $")

                    staging_objs.append(
                        RentalStaging(
                            vendor_name=vendor_name,
                            vendor_code=type_of_equip[:50],
                            equipment_id=equipment_id[:80],
                            equipment_description=equipment_description[:255],
                            equipment_category=type_of_equip[:120],
                            quantity=1,
                            rate_daily=rate if rate is not None else Decimal("0.00"),
                            currency="USD",
                            on_rent_start=on_rent_start if on_rent_start is not None else monday,
                            on_rent_end=on_rent_end,
                            po_number=po_number[:80],
                            sn_request_number=sn_request[:80],
                            comments=comments,
                            cycle_week=week,
                            cycle_year=TARGET_YEAR,
                            source_file=csv_path.name,
                            submitted_by=submitted_by,
                            status=SubmissionStatus.APPROVED,
                            is_validated=not bool(validation_errors),
                            validation_errors="; ".join(validation_errors),
                        )
                    )

                created_staging = RentalStaging.objects.bulk_create(staging_objs)
                total_staging += len(created_staging)

                # ── Build master objects ─────────────────────────────────────
                master_objs = [
                    RentalMaster(
                        vendor_name=s.vendor_name,
                        vendor_code=s.vendor_code,
                        equipment_id=s.equipment_id,
                        equipment_description=s.equipment_description,
                        equipment_category=s.vendor_code,
                        quantity=s.quantity,
                        rate_daily=s.rate_daily,
                        currency=s.currency,
                        on_rent_start=s.on_rent_start,
                        on_rent_end=s.on_rent_end,
                        po_number=s.po_number,
                        sn_request_number=s.sn_request_number,
                        comments=s.comments,
                        cycle_week=week,
                        cycle_year=TARGET_YEAR,
                        source_file=s.source_file,
                        approved_from=s,
                        approved_by=approver,
                        is_active=True,
                    )
                    for s in created_staging
                ]
                RentalMaster.objects.bulk_create(master_objs)
                total_master += len(master_objs)

                # ── VendorAudit per vendor ───────────────────────────────────
                vendors_in_week = {
                    (row.get("RENTAL CO.") or "").strip()
                    for row in week_rows
                    if (row.get("RENTAL CO.") or "").strip()
                }
                submit_time = timezone.make_aware(
                    datetime.datetime.combine(monday, datetime.time(9, 0))
                )
                for vendor in vendors_in_week:
                    VendorAudit.objects.update_or_create(
                        vendor_name=vendor,
                        cycle_date=monday,
                        defaults={
                            "verified":     True,
                            "is_late":      False,
                            "submitted_at": submit_time,
                            "notes":        f"Week {week} data imported from {csv_path.name}.",
                        },
                    )
                    total_audit += 1

                self.stdout.write(
                    f"  Week {week:>2} ({monday}): "
                    f"{len(created_staging):>5} staging / master rows, "
                    f"{len(vendors_in_week):>2} vendors audited"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone.  {total_staging} staging rows, "
                f"{total_master} master rows, "
                f"{total_audit} vendor audit entries."
            )
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _read_csv(self, csv_path: Path) -> list[dict]:
        last_error = None
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                with csv_path.open("r", newline="", encoding=encoding) as fh:
                    return list(csv.DictReader(fh))
            except UnicodeDecodeError as exc:
                last_error = exc
        raise CommandError(f"Cannot decode CSV: {last_error}")

    def _parse_int(self, value) -> int | None:
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            return None

    def _parse_date(self, value) -> datetime.date | None:
        if not value:
            return None
        text = str(value).strip()
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_decimal(self, value) -> Decimal | None:
        text = str(value or "").strip().lstrip("$").replace(",", "").strip()
        if not text:
            return None
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None

    def _find_user(self, username: str) -> "User | None":
        if not username:
            return None
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None
