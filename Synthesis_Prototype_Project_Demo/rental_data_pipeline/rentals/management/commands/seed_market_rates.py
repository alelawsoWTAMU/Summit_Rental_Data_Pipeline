"""
seed_market_rates.py

Populate EquipmentMarketRate with realistic purchase prices and estimated
maintenance costs for all equipment descriptions found in rental_master.

Threshold formula:
  rvb_monthly_threshold = ownership_cost + monthly_maintenance
                        = (purchase_price / (life_yrs * 12))
                          + (purchase_price * annual_maint_pct / 12)

Annual maintenance % benchmarks (% of purchase price per year):
  Heavy loaders / excavators / articulated trucks : 13%
  Cranes                                          : 11%
  Backhoes, telehandlers, skid steers             : 10%
  Vacuum / specialty trucks, sweepers, compressors: 10%
  Light vehicles (pickups, vans, UTV)             :  8%
  Small equipment (light towers, welding, gen.)   : 10%
  Temporary structures / trailers                  :  5%

Usage:
    python manage.py seed_market_rates
    python manage.py seed_market_rates --reset
"""

import datetime
from django.core.management.base import BaseCommand
from rentals.models import EquipmentMarketRate, RentalMaster

# ---------------------------------------------------------------------------
# Equipment rates with corrected approved category names.
# (buy_price, life_yrs, mkt_daily, category, annual_maint_pct)
# annual_maint_pct expressed as a decimal fraction, e.g. 0.13 = 13 %
# ---------------------------------------------------------------------------
RATES = {
    "LOADER CATERPILLAR - 980H":                (550_000,  7, 950,   "Loader",                0.13),
    "LOADER CATERPILLAR - 988H":                (720_000,  7, 1_200, "Loader",                0.13),
    "LOADER CATERPILLAR - 988K":                (750_000,  7, 1_250, "Loader",                0.13),
    "LOADER CATERPILLAR -IT938H":               (390_000,  7, 680,   "Loader",                0.13),
    "LOADER CATERPILLAR - 972M":                (420_000,  7, 720,   "Loader",                0.13),
    "LOADER CATERPILLAR - 966H":                (410_000,  7, 700,   "Loader",                0.13),
    "LOADER CATERPILLAR - 950H":                (320_000,  7, 560,   "Loader",                0.13),
    "CAT EXCAVATOR - 352":                      (480_000,  8, 820,   "Excavator",             0.13),
    "COMBINATION BACKHOE CATERPILLAR - 420E IT":(130_000,  8, 225,   "Loader",                0.10),
    "ARTIC TRUCK 40 TON VOLVO - A40D":          (620_000,  8, 1_050, "Dump Truck",            0.13),
    "Broderson RT-300-2G":                      (175_000, 10, 300,   "Crane",                 0.11),
    "Broderson RT-400":                         (240_000, 10, 410,   "Crane",                 0.11),
    "CARRY DECK CRANE IC-200-3F":               (155_000, 10, 265,   "Crane",                 0.11),
    "BOX VACUUM 25YD":                          (310_000,  8, 530,   "Box Vacuum",            0.10),
    "TL1255":                                   (110_000,  7, 190,   "Telehandler",           0.10),
    "S70 Bobcat skid steer":                    ( 65_000,  7, 115,   "Skid Steer",            0.10),
    "4 Bulb Light Tower":                       ( 10_500,  8,  18,   "Light Tower",           0.10),
    "riding sweeper":                           ( 32_000,  6,  55,   "Sweeper",               0.10),
    "TRUCK SPREADER HOPPER 8 FT 2 CU YD":      ( 58_000,  7, 100,   "Truck Spreader",        0.10),
    "1/2 TON CC 4X4":                           ( 52_000,  5,  90,   "Pickup Truck",          0.08),
    "1/2 TON REG CAB":                          ( 40_000,  5,  70,   "Pickup Truck",          0.08),
    "3/4 TON CC 4X4":                           ( 60_000,  5, 105,   "Pickup Truck",          0.08),
    "027-0365 250 AMP CC SKYWELDER PKG":        ( 15_000,  7,  26,   "Welding Equipment",     0.10),
    "6000 PNEU DC":                             ( 48_000,  8,  82,   "Air Compressor & Attachments", 0.10),
    "Mobile Trailer":                           ( 85_000, 10, 145,   "Mobile Trailer",        0.05),
    "Mini Picker":                              ( 28_000,  8,  48,   "Mini Picker",           0.11),
    "059-0570 UTILITY VEHICLE 4 SEAT 4WD GAS CAB": (22_000, 5, 38,  "UTV",                   0.08),
}

# ---------------------------------------------------------------------------
# All 60 approved equipment categories.
# A stub EquipmentMarketRate row is created for any category not already
# covered by a RATES entry, so the vendor portal dropdown is always complete.
# Stub rows use placeholder financials (0) and are excluded from RVB reports
# by the source_notes sentinel value "__category_stub__".
# ---------------------------------------------------------------------------
APPROVED_CATEGORIES = [
    "Air Compressor & Attachments",
    "Air Dryer",
    "Boom Lift",
    "Box Vacuum",
    "Broce Broom",
    "Cart",
    "Clarifier",
    "Coil Truck",
    "Crane",
    "Dozer",
    "Drive Variable Frequency",
    "Dump Truck",
    "Excavator",
    "Fire Extinguisher",
    "Fitting",
    "Flatbed Truck",
    "Forklift",
    "Generator",
    "Grader",
    "Heater",
    "Hose",
    "Level Monitoring",
    "Light Tower",
    "Loader",
    "Manlift",
    "Material Handler",
    "Mini Picker",
    "Mini Skid Steer",
    "Mobile Trailer",
    "Pickup Truck",
    "Pump",
    "Pump Accessories",
    "Rail Car",
    "Reach Truck",
    "Refractory Tearout Machine",
    "Scissor Lift",
    "Scrubber",
    "Semi Truck",
    "Skid Steer",
    "Spillguard",
    "Stake Bed Truck",
    "Suction Screen",
    "Sweeper",
    "Tank Accessories",
    "Tank Mini Frac",
    "Tank Mixer",
    "Tank Poly",
    "Tank Standard Steel",
    "Telehandler",
    "Track Loader",
    "Tractor",
    "Truck Snow",
    "Truck Spreader",
    "UTV",
    "Van",
    "Vehicle Attachments",
    "Walkie Pallet Stacker",
    "Washer",
    "Welding Equipment",
    "Other",
]

EFFECTIVE_DATE = datetime.date(2026, 1, 1)


class Command(BaseCommand):
    help = "Seed EquipmentMarketRate with estimated purchase prices and all approved category stubs."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Clear existing records first.")

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = EquipmentMarketRate.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing records.")

        # Also pick up any descriptions in master that aren't in our explicit list
        in_master = set(
            RentalMaster.objects.values_list("equipment_description", flat=True).distinct()
        )

        created = 0
        skipped = 0
        for desc, (buy_price, life, mkt_daily, category, maint_pct) in RATES.items():
            daily_threshold    = round(buy_price / (life * 260), 2)
            monthly_ownership  = round(buy_price / (life * 12), 2)
            monthly_maint      = round(buy_price * maint_pct / 12, 2)
            monthly_threshold  = round(monthly_ownership + monthly_maint, 2)
            obj, was_created = EquipmentMarketRate.objects.update_or_create(
                equipment_description=desc,
                defaults={
                    "equipment_category":        category,
                    "estimated_purchase_price":  buy_price,
                    "useful_life_years":          life,
                    "market_daily_rate":          mkt_daily,
                    "rvb_daily_threshold":        daily_threshold,
                    "rvb_monthly_threshold":      monthly_threshold,
                    "annual_maintenance_pct":     maint_pct,
                    "monthly_maintenance_cost":   monthly_maint,
                    "effective_date":             EFFECTIVE_DATE,
                    "source_notes":               (
                        f"Ownership: ${monthly_ownership:,.0f}/mo  "
                        f"+ Maint ({maint_pct*100:.0f}%/yr): ${monthly_maint:,.0f}/mo  "
                        f"= Threshold: ${monthly_threshold:,.0f}/mo. "
                        f"Industry benchmark for steel-mill facility, 2026."
                    ),
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        # ── Category stubs ──────────────────────────────────────────────────
        # Ensure every approved category appears in the dropdown even if no
        # real equipment rate exists yet.  Stubs are identified by the
        # "__category_stub__" sentinel in source_notes and are excluded from
        # RVB candidate reports.
        stubs_created  = 0
        stubs_skipped  = 0
        covered = set(
            EquipmentMarketRate.objects.exclude(equipment_category="")
            .values_list("equipment_category", flat=True).distinct()
        )
        for cat in APPROVED_CATEGORIES:
            if cat in covered:
                stubs_skipped += 1
                continue
            EquipmentMarketRate.objects.get_or_create(
                equipment_description=f"[stub] {cat}",
                defaults={
                    "equipment_category":       cat,
                    "estimated_purchase_price": 0,
                    "useful_life_years":        1,
                    "market_daily_rate":        0,
                    "rvb_daily_threshold":      0,
                    "rvb_monthly_threshold":    0,
                    "annual_maintenance_pct":   0,
                    "monthly_maintenance_cost": 0,
                    "effective_date":           EFFECTIVE_DATE,
                    "source_notes":             "__category_stub__",
                },
            )
            stubs_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Rates: {created} created, {skipped} updated. "
            f"Category stubs: {stubs_created} created, {stubs_skipped} already covered. "
            f"Coverage: {len(set(RATES.keys()) & in_master)}/{len(in_master)} master descriptions matched."
        ))
