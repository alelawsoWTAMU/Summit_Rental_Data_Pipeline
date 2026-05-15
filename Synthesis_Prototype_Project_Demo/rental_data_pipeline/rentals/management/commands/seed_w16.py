"""
seed_w16.py

Seed Week 16 (2026-W16, Monday 2026-04-13) into RentalMaster and RentalStaging
using Week 15 as the base, with realistic variance:

  • ~10% of W15 lines are dropped to simulate equipment taken off rent.
  • 10 new equipment lines are added across existing vendors to simulate
    newly placed-on-rent items.
  • VendorAudit entries are created with verified=True (submission already due).

Usage:
    python manage.py seed_w16                  # idempotent (skips if W16 exists)
    python manage.py seed_w16 --reset          # wipe W16 first, then seed
"""

import datetime
import random
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from rentals.models import (
    RentalMaster,
    RentalStaging,
    SubmissionStatus,
    UserProfile,
    VendorAudit,
)

User = get_user_model()

TARGET_YEAR  = 2026
TARGET_WEEK  = 16
SOURCE_YEAR  = 2026
SOURCE_WEEK  = 15
MONDAY_W16   = datetime.date.fromisocalendar(TARGET_YEAR, TARGET_WEEK, 1)  # 2026-04-13

SEED = 16  # separate RNG seed from history (42) for distinct results
DROPOUT_RATE = 0.10  # ~10% of W15 lines removed

# ---------------------------------------------------------------------------
# New equipment to inject — placed on-rent in W16 but NOT present in W15
# Columns: vendor_name, equipment_id, equipment_description, type_code,
#          rate_daily (monthly), on_rent_start, on_rent_end, po_number
# ---------------------------------------------------------------------------
_NEW_EQUIPMENT = [
    {
        "vendor_name":            "Marshall Group",
        "equipment_id":           "MG-77391",
        "equipment_description":  "45-Ton Rough Terrain Crane",
        "type_code":              "CRANE",
        "rate_daily":             Decimal("8400.00"),
        "on_rent_start":          datetime.date(2026, 4, 13),
        "on_rent_end":            datetime.date(2026, 7, 11),
        "po_number":              "PO-2026-0491",
    },
    {
        "vendor_name":            "Marshall Group",
        "equipment_id":           "MG-77392",
        "equipment_description":  "Telescopic Boom Lift — 86 ft",
        "type_code":              "LIFT",
        "rate_daily":             Decimal("4950.00"),
        "on_rent_start":          datetime.date(2026, 4, 14),
        "on_rent_end":            None,
        "po_number":              "PO-2026-0492",
    },
    {
        "vendor_name":            "Brown Group",
        "equipment_id":           "BG-1138",
        "equipment_description":  "375 CFM Diesel Air Compressor",
        "type_code":              "COMPRESSOR",
        "rate_daily":             Decimal("3200.00"),
        "on_rent_start":          datetime.date(2026, 4, 13),
        "on_rent_end":            datetime.date(2026, 6, 13),
        "po_number":              "PO-2026-0488",
    },
    {
        "vendor_name":            "Brown Group",
        "equipment_id":           "BG-1139",
        "equipment_description":  "800 kW Diesel Generator",
        "type_code":              "GENERATOR",
        "rate_daily":             Decimal("14500.00"),
        "on_rent_start":          datetime.date(2026, 4, 15),
        "on_rent_end":            None,
        "po_number":              "PO-2026-0489",
    },
    {
        "vendor_name":            "Smith LLC",
        "equipment_id":           "SL-20241",
        "equipment_description":  "Multi-Process Welder",
        "type_code":              "WELDER",
        "rate_daily":             Decimal("1850.00"),
        "on_rent_start":          datetime.date(2026, 4, 13),
        "on_rent_end":            datetime.date(2026, 5, 25),
        "po_number":              "PO-2026-0495",
    },
    {
        "vendor_name":            "Smith LLC",
        "equipment_id":           "SL-20242",
        "equipment_description":  "Engine-Driven Welder/Generator",
        "type_code":              "WELDER",
        "rate_daily":             Decimal("2600.00"),
        "on_rent_start":          datetime.date(2026, 4, 14),
        "on_rent_end":            None,
        "po_number":              "PO-2026-0496",
    },
    {
        "vendor_name":            "Harris LLC",
        "equipment_id":           "HL-4411",
        "equipment_description":  "200-Ton Crawler Crane",
        "type_code":              "CRANE",
        "rate_daily":             Decimal("32000.00"),
        "on_rent_start":          datetime.date(2026, 4, 13),
        "on_rent_end":            datetime.date(2026, 10, 10),
        "po_number":              "PO-2026-0481",
    },
    {
        "vendor_name":            "Harris LLC",
        "equipment_id":           "HL-4412",
        "equipment_description":  "Rigging Skid Package — Hydraulic Gantry 50T",
        "type_code":              "RIGGING",
        "rate_daily":             Decimal("6800.00"),
        "on_rent_start":          datetime.date(2026, 4, 13),
        "on_rent_end":            datetime.date(2026, 8, 31),
        "po_number":              "PO-2026-0482",
    },
    {
        "vendor_name":            "Griffin Ltd",
        "equipment_id":           "GL-8851",
        "equipment_description":  "24x60 Modular Office Complex — 4-Unit Interconnect",
        "type_code":              "TEMP FACILITY",
        "rate_daily":             Decimal("5200.00"),
        "on_rent_start":          datetime.date(2026, 4, 14),
        "on_rent_end":            datetime.date(2026, 12, 31),
        "po_number":              "PO-2026-0502",
    },
    {
        "vendor_name":            "Myers Inc",
        "equipment_id":           "MI-3309",
        "equipment_description":  "4-Yard Debris Box Hopper (additional unit — pit area expansion)",
        "type_code":              "SWEEPING",
        "rate_daily":             Decimal("1100.00"),
        "on_rent_start":          datetime.date(2026, 4, 13),
        "on_rent_end":            None,
        "po_number":              "PO-2026-0499",
    },
]


class Command(BaseCommand):
    help = "Seed Week 16 (2026) into RentalMaster and RentalStaging with W15-derived variance."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing W16 staging, master, and audit rows before seeding.",
        )

    def handle(self, *args, **options):
        rng = random.Random(SEED)
        approver = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.first()
        )

        # Guard against accidental double-seeding
        if not options["reset"]:
            if RentalMaster.objects.filter(cycle_year=TARGET_YEAR, cycle_week=TARGET_WEEK).exists():
                self.stdout.write(self.style.WARNING(
                    f"W{TARGET_WEEK} {TARGET_YEAR} already exists in RentalMaster. "
                    "Run with --reset to overwrite."
                ))
                return

        # ── Load W15 pool from RentalMaster ──────────────────────────────
        w15_pool = list(
            RentalMaster.objects.filter(
                cycle_year=SOURCE_YEAR, cycle_week=SOURCE_WEEK, is_active=True
            ).values(
                "vendor_name", "vendor_code", "equipment_id",
                "equipment_description", "quantity", "rate_daily",
                "currency", "on_rent_start", "on_rent_end",
                "po_number", "sn_request_number",
            )
        )
        if not w15_pool:
            self.stderr.write(self.style.ERROR(
                f"No W{SOURCE_WEEK} RentalMaster rows found. Run seed_history first."
            ))
            return

        # ── Deterministically drop ~10% (sorted for reproducibility) ─────
        sorted_pool = sorted(w15_pool, key=lambda r: (r["vendor_name"], r["equipment_id"]))
        w16_carries = [r for r in sorted_pool if rng.random() >= DROPOUT_RATE]
        dropped = len(sorted_pool) - len(w16_carries)

        # Slight rate drift on 3% of carried rows
        for r in w16_carries:
            if rng.random() < 0.03:
                factor = Decimal(str(round(rng.uniform(0.98, 1.02), 4)))
                r["rate_daily"] = (r["rate_daily"] * factor).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

        with transaction.atomic():
            if options["reset"]:
                ds, _ = RentalStaging.objects.filter(
                    cycle_year=TARGET_YEAR, cycle_week=TARGET_WEEK
                ).delete()
                dm, _ = RentalMaster.objects.filter(
                    cycle_year=TARGET_YEAR, cycle_week=TARGET_WEEK
                ).delete()
                da, _ = VendorAudit.objects.filter(
                    cycle_date=MONDAY_W16
                ).delete()
                self.stdout.write(
                    f"Reset: {ds} staging, {dm} master, {da} audit rows deleted."
                )

            # ── Build staging + master rows from carried pool ─────────────
            staging_objs  = []
            master_objs   = []

            for r in w16_carries:
                sv = self._find_vendor_user(r["vendor_name"])
                staging_objs.append(RentalStaging(
                    vendor_name=r["vendor_name"],
                    vendor_code=(r["vendor_code"] or "")[:50],
                    equipment_id=(r["equipment_id"] or "")[:80],
                    equipment_description=(r["equipment_description"] or "")[:255],
                    quantity=r["quantity"],
                    rate_daily=r["rate_daily"],
                    currency=r["currency"] or "USD",
                    on_rent_start=r["on_rent_start"] or MONDAY_W16,
                    on_rent_end=r["on_rent_end"],
                    po_number=(r["po_number"] or "")[:80],
                    sn_request_number=(r["sn_request_number"] or "")[:80],
                    cycle_week=TARGET_WEEK,
                    cycle_year=TARGET_YEAR,
                    source_file=f"seed_w16_{TARGET_YEAR}",
                    submitted_by=sv,
                    status=SubmissionStatus.APPROVED,
                    is_validated=True,
                    validation_errors="",
                ))

            created_staging = RentalStaging.objects.bulk_create(staging_objs)

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
                    cycle_week=TARGET_WEEK,
                    cycle_year=TARGET_YEAR,
                    source_file=s.source_file,
                    approved_from=s,
                    approved_by=approver,
                    is_active=True,
                ))
            RentalMaster.objects.bulk_create(master_objs)

            # ── Inject new equipment lines ────────────────────────────────
            new_staging  = []
            new_master   = []

            for eq in _NEW_EQUIPMENT:
                sv = self._find_vendor_user(eq["vendor_name"])
                ns = RentalStaging.objects.create(
                    vendor_name=eq["vendor_name"],
                    vendor_code=eq["type_code"][:50],
                    equipment_id=eq["equipment_id"][:80],
                    equipment_description=eq["equipment_description"][:255],
                    quantity=1,
                    rate_daily=eq["rate_daily"],
                    currency="USD",
                    on_rent_start=eq["on_rent_start"],
                    on_rent_end=eq["on_rent_end"],
                    po_number=eq["po_number"][:80],
                    sn_request_number="",
                    comments="New rental — placed on-rent W16.",
                    cycle_week=TARGET_WEEK,
                    cycle_year=TARGET_YEAR,
                    source_file=f"seed_w16_{TARGET_YEAR}",
                    submitted_by=sv,
                    status=SubmissionStatus.APPROVED,
                    is_validated=True,
                    validation_errors="",
                )
                new_staging.append(ns)
                new_master.append(RentalMaster(
                    vendor_name=ns.vendor_name,
                    vendor_code=ns.vendor_code,
                    equipment_id=ns.equipment_id,
                    equipment_description=ns.equipment_description,
                    quantity=1,
                    rate_daily=ns.rate_daily,
                    currency="USD",
                    on_rent_start=ns.on_rent_start,
                    on_rent_end=ns.on_rent_end,
                    po_number=ns.po_number,
                    sn_request_number="",
                    cycle_week=TARGET_WEEK,
                    cycle_year=TARGET_YEAR,
                    source_file=ns.source_file,
                    approved_from=ns,
                    approved_by=approver,
                    is_active=True,
                ))
            RentalMaster.objects.bulk_create(new_master)

            # ── VendorAudit — all verified (W16 is a closed week) ─────────
            all_vendors = sorted(
                {r["vendor_name"] for r in w16_carries}
                | {eq["vendor_name"] for eq in _NEW_EQUIPMENT}
            )
            for vendor in all_vendors:
                submitted_day = MONDAY_W16 + datetime.timedelta(days=rng.randint(0, 3))
                VendorAudit.objects.update_or_create(
                    vendor_name=vendor,
                    cycle_date=MONDAY_W16,
                    defaults={
                        "vendor_user":  self._find_vendor_user(vendor),
                        "verified":     True,
                        "is_late":      False,
                        "submitted_at": timezone.make_aware(
                            datetime.datetime.combine(
                                submitted_day,
                                datetime.time(rng.randint(7, 17), rng.randint(0, 59)),
                            )
                        ),
                        "notes": f"W{TARGET_WEEK} submission verified.",
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ W{TARGET_WEEK} {TARGET_YEAR} seeded:"
        ))
        self.stdout.write(f"  Carried from W{SOURCE_WEEK}: {len(w16_carries)} records")
        self.stdout.write(f"  Dropped (off-rent):          {dropped} records")
        self.stdout.write(f"  New equipment added:         {len(_NEW_EQUIPMENT)} records")
        self.stdout.write(f"  Vendors audited:             {len(all_vendors)}")

    # ------------------------------------------------------------------ #

    def _find_vendor_user(self, vendor_name):
        profile = (
            UserProfile.objects.select_related("user", "company")
            .filter(role="vendor", company__name=vendor_name)
            .first()
        )
        return profile.user if profile else None
