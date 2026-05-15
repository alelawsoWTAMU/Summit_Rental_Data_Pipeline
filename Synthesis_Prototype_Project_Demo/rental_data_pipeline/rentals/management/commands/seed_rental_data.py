import csv
import random
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from rentals.models import RentalStaging, SubmissionStatus, UserProfile, VendorAudit


User = get_user_model()

_COMMENTS_POOL = [
    "Rate negotiated down from original quote — see email chain.",
    "Unit on standby; minimal hours logged this period.",
    "Awaiting PO amendment — original PO exhausted.",
    "Operator reported minor hydraulic leak; vendor notified.",
    "Extended per field request; original end date was earlier.",
    "Verify serial number against delivery receipt before approving.",
    "Duplicate equipment ID suspected — flagged for procurement review.",
    "Rate includes fuel surcharge per vendor agreement.",
    "Unit returned early; credit memo expected from vendor.",
    "SN request pending IT ticket resolution.",
    "Confirmed on-site as of last week's field inspection.",
    "Crew mobilization delayed; start date pushed two weeks.",
    "Month-to-month — no fixed end date agreed.",
    "Reviewed and approved by project manager on-site.",
    "Rate subject to renegotiation at 90-day mark.",
]

_RNG = random.Random(42)  # fixed seed for reproducible dummy data


class Command(BaseCommand):
    help = "Seed RentalStaging and VendorAudit from dummy CSV data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=str(Path(settings.BASE_DIR).parent / "docs" / "Rental_Report_DUMMY.csv"),
            help="Path to dummy rental CSV.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing staging and audit rows before seeding.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"]).resolve()
        do_reset = options["reset"]

        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        rows = self._read_rows(csv_path)
        if not rows:
            raise CommandError("CSV has no data rows.")

        with transaction.atomic():
            if do_reset:
                RentalStaging.objects.all().delete()
                VendorAudit.objects.all().delete()

            staged_count = 0
            invalid_count = 0
            latest_date_by_vendor = {}

            # Always stamp rows with the current ISO week so the review page shows them
            import datetime as _dt
            _today_iso = _dt.date.today().isocalendar()
            seed_year, seed_week = _today_iso[0], _today_iso[1]

            for row in rows:
                vendor_name = (row.get("RENTAL_COMPANY") or "").strip()
                if not vendor_name:
                    continue

                equipment_id = (row.get("EQUIPMENT #") or "").strip() or "UNKNOWN"
                equipment_description = (row.get("EQUIPMENT DESCRIPTION") or "").strip() or "Unknown"
                type_of_equipment = (row.get("TYPE OF EQUIPMENT") or "").strip()
                started = self._parse_date(row.get("DATE RENTAL STARTED"))
                ended = self._parse_date(row.get("PROJECTED END DATE"))
                date_anchor = self._parse_date(row.get("DATE"))
                rate = self._parse_decimal(row.get("MONTHLY RATE $") or "0")
                po_number = (row.get("PO NUMBER") or "").strip()
                sn_request_number = (row.get("Service Now Request #") or "").strip()
                try:
                    csv_cycle_week = int(row.get("WEEK_NUMBER") or 0) or None
                    csv_cycle_year = int(row.get("YEAR") or 0) or None
                except (ValueError, TypeError):
                    csv_cycle_week = None
                    csv_cycle_year = None

                # Override CSV week/year with today's ISO values so data appears in current week
                csv_cycle_week = seed_week
                csv_cycle_year = seed_year

                validation_errors = []
                if started is None:
                    validation_errors.append("Invalid DATE RENTAL STARTED")
                if rate is None:
                    validation_errors.append("Invalid MONTHLY RATE $")

                submitted_by = self._find_vendor_user(vendor_name)

                # ~1-in-6 rows get a realistic comment
                comment_text = _RNG.choice(_COMMENTS_POOL) if _RNG.randint(1, 6) == 1 else ""

                RentalStaging.objects.create(
                    vendor_name=vendor_name,
                    vendor_code=type_of_equipment[:50],
                    equipment_id=equipment_id[:80],
                    equipment_description=equipment_description[:255],
                    quantity=1,
                    rate_daily=rate if rate is not None else Decimal("0.00"),
                    currency="USD",
                    on_rent_start=started if started is not None else timezone.now().date(),
                    on_rent_end=ended,
                    po_number=po_number[:80],
                    sn_request_number=sn_request_number[:80],
                    comments=comment_text,
                    cycle_week=csv_cycle_week,
                    cycle_year=csv_cycle_year,
                    source_file=csv_path.name,
                    submitted_by=submitted_by,
                    status=(
                        SubmissionStatus.SUBMITTED
                        if not validation_errors
                        else SubmissionStatus.PENDING
                    ),
                    is_validated=not validation_errors,
                    validation_errors="; ".join(validation_errors),
                )
                staged_count += 1
                if validation_errors:
                    invalid_count += 1

                if date_anchor:
                    prev = latest_date_by_vendor.get(vendor_name)
                    if prev is None or date_anchor > prev:
                        latest_date_by_vendor[vendor_name] = date_anchor

            self._upsert_vendor_audits(latest_date_by_vendor)

        self.stdout.write(self.style.SUCCESS("Rental data seeded successfully."))
        self.stdout.write(f"Rows created in staging: {staged_count}")
        self.stdout.write(f"Rows with validation issues: {invalid_count}")
        self.stdout.write(f"Vendor audit rows upserted: {len(latest_date_by_vendor)}")

    def _read_rows(self, csv_path: Path):
        last_error = None
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                with csv_path.open("r", newline="", encoding=encoding) as csv_file:
                    return list(csv.DictReader(csv_file))
            except UnicodeDecodeError as exc:
                last_error = exc
        raise CommandError(f"Unable to decode CSV file: {last_error}")

    def _parse_date(self, value):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None

        date_formats = [
            "%m/%d/%Y",
            "%m/%d/%Y %H:%M",
            "%m/%d/%y",
        ]
        for fmt in date_formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_decimal(self, value):
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None

    def _find_vendor_user(self, vendor_name):
        profile = (
            UserProfile.objects.select_related("user", "company")
            .filter(role="vendor", company__name=vendor_name)
            .first()
        )
        return profile.user if profile else None

    def _upsert_vendor_audits(self, latest_date_by_vendor):
        import datetime as _dt
        # cycle_date must be the Monday of the current ISO week — same formula the view uses
        _today = _dt.date.today().isocalendar()
        cycle_date = _dt.date.fromisocalendar(_today[0], _today[1], 1)

        for vendor_name in latest_date_by_vendor:
            profile = (
                UserProfile.objects.select_related("user", "company")
                .filter(role="vendor", company__name=vendor_name)
                .first()
            )
            vendor_user = profile.user if profile else None

            VendorAudit.objects.update_or_create(
                vendor_name=vendor_name,
                cycle_date=cycle_date,
                defaults={
                    "vendor_user": vendor_user,
                    "verified": True,
                    "is_late": False,
                    "logged_in_at": timezone.now(),
                    "submitted_at": timezone.now(),
                    "notes": "Seeded from dummy CSV",
                },
            )
