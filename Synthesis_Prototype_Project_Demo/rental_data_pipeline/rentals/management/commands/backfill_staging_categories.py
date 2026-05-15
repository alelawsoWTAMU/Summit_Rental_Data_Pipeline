"""
Management command: backfill_staging_categories
Assigns an approved equipment_category to every RentalStaging row
that currently has a blank category.

Usage:
    python manage.py backfill_staging_categories
    python manage.py backfill_staging_categories --dry-run
"""

from django.core.management.base import BaseCommand
from rentals.models import RentalMaster, RentalStaging

# ── Exact description → category mapping ─────────────────────────────────────
EXACT: dict[str, str] = {
    # Air compressors & dryers
    "185 CFM air compressor":                        "Air Compressor & Attachments",
    "185 Compressor":                                "Air Compressor & Attachments",
    "185 compressor":                                "Air Compressor & Attachments",
    "375 CFM Diesel Air Compressor":                 "Air Compressor & Attachments",
    "375 CFM air compressor":                        "Air Compressor & Attachments",
    "375 compressor":                                "Air Compressor & Attachments",
    "1500 CFM Compressor No Dryer & Accessories":    "Air Compressor & Attachments",
    "1500 CFM Compressor w/Dryer & Accessories":     "Air Compressor & Attachments",
    "1600 CFM Compressor w/Dryer & Accessories":     "Air Compressor & Attachments",
    "450 CFM Dryer":                                 "Air Dryer",
    # Boom lifts
    "125 Straight boom lift":                        "Boom Lift",
    "135ft Boom Lift with jib":                      "Boom Lift",
    "30 Electric Boom Lift":                         "Boom Lift",
    "30ft Articulating Boom Lift":                   "Boom Lift",
    "40 Electric Boom Lift":                         "Boom Lift",
    "45 Articulated Boom lift":                      "Boom Lift",
    "450AJ Articulated Boom lift":                   "Boom Lift",
    "45ft RT ART BM - 450AJ, DSL, G/W":             "Boom Lift",
    "60ft BM - S-60X, DSL, FF, G/W":                "Boom Lift",
    "60ft BM ART - 600AJ, DSL, G/W, FF":            "Boom Lift",
    "60ft RT Articulating Boom Lift":                "Boom Lift",
    "62ft RT Articulating Boom Lift":                "Boom Lift",
    "34ft Elec Art BM - Z34/22N, NM/T":             "Boom Lift",
    "80ft RT ART BM - Z80/60, DSL, FF, G/W":        "Boom Lift",
    "800AJ Articulated Boom lift":                   "Boom Lift",
    "S45 Straight boom lift":                        "Boom Lift",
    "S65 Straight boom lift":                        "Boom Lift",
    "S85 Straight boom lift":                        "Boom Lift",
    "Telescopic Boom Lift — 86 ft":                  "Boom Lift",
    "UL 120ft BM w/Jib - 1200SJP, FF, G/W, SGD":   "Boom Lift",
    "Z30 Electric Boom Lift":                        "Boom Lift",
    "Z45 Articulated Boom lift":                     "Boom Lift",
    "Z60 Articulated Boom lift":                     "Boom Lift",
    "Z80 Articulated Boom lift":                     "Boom Lift",
    "JLG 600S":                                      "Boom Lift",
    "058-0607 60ft ART MANLIFT W/JIB":              "Boom Lift",
    "058-0803 80ft ART MANLIFT W/JIB":              "Boom Lift",
    "058-0880 135ft ART MANLIFT W/JIB":             "Boom Lift",
    # Box vacuum
    "Box Vacuum 25YD":                               "Box Vacuum",
    # Carts
    "4 seat gas cab cart":                           "Cart",
    "large 2 passager cab cart":                     "Cart",
    # Clarifier
    "X-Flo Mobile Clarifier":                        "Clarifier",
    # Coil truck
    "COIL TRUCK WESTERNSTAR - 4900SB":               "Coil Truck",
    # Cranes
    "200-Ton Crawler Crane":                         "Crane",
    "295 Mini Crane":                                "Mini Picker",
    "45-Ton Rough Terrain Crane":                    "Crane",
    "3950 Manitowoc":                                "Crane",
    "Broderson IC-200":                              "Mini Picker",
    "CARRY DECK CRANE IC80-3F":                      "Crane",
    "Grove RT530E-2":                                "Crane",
    "Grove RT540E":                                  "Crane",
    "Link-Belt RTC-8065":                            "Crane",
    "Tadano GR-1000XL":                              "Crane",
    "Tadano GR-350XL-3":                             "Crane",
    "Tadano GR-800XL-4":                             "Crane",
    "Terex RT230-1":                                 "Crane",
    "Terex RT230-2":                                 "Crane",
    "Rigging Skid Package — Hydraulic Gantry 50T":  "Crane",
    # Dozers
    "052-0200 200-250HP CRAWLER DOZER LGP":          "Dozer",
    "052-1605 DOZER RIPPER 140-159HP CLASS":         "Dozer",
    "D8 Dozer W/Shank Ripper":                       "Dozer",
    "DOZER CATERPILLAR - D8":                        "Dozer",
    "CAT CS74 - PADDED":                             "Dozer",
    "CAT CS74 - SMOOTH":                             "Dozer",
    # Drive Variable Frequency
    "Drive Variable Frequency 20HP":                 "Drive Variable Frequency",
    # Dump trucks (articulated)
    "ARTIC TRUCK 60 TON VOLVO - A60":               "Dump Truck",
    "CATERPILLAR 740B ARTIC TRUCK":                  "Dump Truck",
    "CATERPILLAR 745C ARTIC TRUCK":                  "Dump Truck",
    # Excavators
    "EXCAVATOR CAT 325DL":                           "Excavator",
    # Fittings
    "4 NIPPLE":                                      "Fitting",
    "Adapter 2 Male Cam x FNPT AL":                  "Fitting",
    "Adapter 4 Female Cam x FNPT AL":                "Fitting",
    "Adapter 4 Male Cam x MNPT AL":                  "Fitting",
    "Adapter 6 Flange x FNPT 150# STL":              "Fitting",
    "Adapter Reducing 6x4 Concentric Flange STL":    "Fitting",
    "Elbow 6 90 Degree Female Cam x Male Cam AL":    "Fitting",
    # Flatbed trucks
    "FLATBED 20 TON  INTERNATIONAL NAVISTAR 4400":   "Flatbed Truck",
    "FLATBED 20 TON INTERNATIONAL NAVISTAR 4400":    "Flatbed Truck",
    "FLATBED 20 TON PETERBILT":                      "Flatbed Truck",
    "FLATBED TRUCK":                                 "Flatbed Truck",
    "9 FLATBED EX CAB":                              "Flatbed Truck",
    "DODGE 5500 BUCKET TRUCK":                       "Flatbed Truck",
    # Forklifts
    "ELECTRIC":                                      "Forklift",
    "8 Diesel":                                      "Forklift",
    "3,000 LB ELC":                                  "Forklift",
    "3,000 LB ELEC":                                 "Forklift",
    "3,500 LB ELEC":                                 "Forklift",
    "3,500 LB PNEU LPG":                             "Forklift",
    "3000 ELECTRIC":                                 "Forklift",
    "4000 Elect":                                    "Forklift",
    "5000 Elect":                                    "Forklift",
    "5000 PNEU D":                                   "Forklift",
    "5000 PNEU LP":                                  "Forklift",
    "5000 Pneu LP":                                  "Forklift",
    "5000 SHORT MAST":                               "Forklift",
    "6,000 LB ELECTRIC":                             "Forklift",
    "6,000 LB PNEU DC":                              "Forklift",
    "6,000 PNEU  D":                                 "Forklift",
    "6,000 PNEU DC":                                 "Forklift",
    "6,000 PNEU LPG":                                "Forklift",
    "6,500 LB PNEU DIE":                             "Forklift",
    "6000 ELEC":                                     "Forklift",
    "6000 Elect":                                    "Forklift",
    "6000 Electric":                                 "Forklift",
    "6000 PNEU D":                                   "Forklift",
    "6000 PNEU DCFP":                                "Forklift",
    "6000 PNEU-DC":                                  "Forklift",
    "6000 Pneu LPG":                                 "Forklift",
    "6000 RT HS":                                    "Forklift",
    "6500 PNEU D":                                   "Forklift",
    "6500 PNEU D C":                                 "Forklift",
    "6500 PNEU DC":                                  "Forklift",
    "6500 PNEU DFP":                                 "Forklift",
    "7,000 PNEU":                                    "Forklift",
    "7000 PNEU LPG":                                 "Forklift",
    "7000 Pneu D":                                   "Forklift",
    "8,000 LB PNEU DC":                              "Forklift",
    "8000 Pneu D":                                   "Forklift",
    "9,000 LB PNEU DC":                              "Forklift",
    "9,000 LB PNEU DCR":                             "Forklift",
    "9,000 PNEU DC":                                 "Forklift",
    "9,000 PNEU DCFP":                               "Forklift",
    "9,000 PNEU DCFPA":                              "Forklift",
    "9000 PNEU D":                                   "Forklift",
    "9000 PNEU DC":                                  "Forklift",
    "9000 Pneu":                                     "Forklift",
    "9000 Pneu D":                                   "Forklift",
    "9000 Pneu DC":                                  "Forklift",
    "10000 PNEU D":                                  "Forklift",
    "11,000 PNEU D":                                 "Forklift",
    "11000 DIE":                                     "Forklift",
    "11000 PNEU DC":                                 "Forklift",
    "12000 PNEU DC":                                 "Forklift",
    "15500 PNEU DFP":                                "Forklift",
    "36000 PNEU DC":                                 "Forklift",
    "55,000 LB PNEU DIE":                            "Forklift",
    "70000 CUSHION":                                 "Forklift",
    "70000 RAM":                                     "Forklift",
    "KONECRANE FORKLIFT SMV-25":                     "Forklift",
    "PALLET CARRIER PALING - CTS 150H":              "Forklift",
    "Taylor X650L":                                  "Forklift",
    "1500 CC":                                       "Pickup Truck",   # Chevy 1500 crew cab
    # Generators
    "(2) 500 AMP Diesels":                           "Generator",
    "60KW Gen Single Phase w/ cable & tails":        "Generator",
    "800 kW Diesel Generator":                       "Generator",
    "XD2000G":                                       "Generator",
    "Sky power":                                     "Generator",
    "300AMP 4-Pack":                                 "Welding Equipment",
    "300AMP Diesel":                                 "Welding Equipment",
    "350AMP 4-Pack":                                 "Welding Equipment",
    "400AMP Diesel":                                 "Welding Equipment",
    "500AMP Diesel":                                 "Welding Equipment",
    # Graders
    "GRADER CATERPILLAR - 143H":                     "Grader",
    "GRADER CATERPILLAR - 160M":                     "Grader",
    # Heaters
    "1.5 Mil BTU":                                   "Heater",
    # Hoses
    "Hose 2x25 HD Tank Truck Camlock 150#":          "Hose",
    "Hose 4x20 HD Tank Truck Camlock 150#":          "Hose",
    "Hose 4x25 HD Tank Truck Camlock 150#":          "Hose",
    "Hose 4x50 Layflat Camlock 150#":               "Hose",
    "Hose 6x25 Braid Flange D x Flange T SS":       "Hose",
    "Hose 6x25 HD Tank Truck Camlock 75#":           "Hose",
    # Level monitoring
    "Gauge Level Radar Battery Operated Gen.3 Omart Vega": "Level Monitoring",
    # Light towers
    "LIGHT TOWER TEREX RL4":                         "Light Tower",
    # Loaders
    "LOADER CATERPILLAR - 930G":                     "Loader",
    "LOADER CATERPILLAR - 966K":                     "Loader",
    "LOADER CATERPILLAR - 988G":                     "Loader",
    # Manlifts (single-person vertical)
    "26 Electric Single Manlift":                    "Manlift",
    # Material handlers
    "SENNEBOGEN 850":                                "Material Handler",
    "COIL RAM TRACTOR 80K LBS":                      "Material Handler",
    "COIL RAM TRACTOR KONECRANE":                    "Material Handler",
    # Mini skid steer
    "CATERPILLAR 259D":                              "Mini Skid Steer",
    # Mobile trailers / offices / containers
    "20FT GLO":                                      "Mobile Trailer",
    "24x60 Modular Office Complex — 4-Unit Interconnect": "Mobile Trailer",
    "36X10":                                         "Mobile Trailer",
    "40FT CONNEX BOX":                               "Mobile Trailer",
    "60X12":                                         "Mobile Trailer",
    "60X24":                                         "Mobile Trailer",
    "72X12":                                         "Mobile Trailer",
    # Pickup trucks
    "1 TON CC  4X2":                                 "Pickup Truck",
    "1 TON CC 4X4":                                  "Pickup Truck",
    "1/4 TON CC 4X4":                                "Pickup Truck",
    "3/4 TON REG CAB 4X4":                           "Pickup Truck",
    "CHEVY 1500 2 DOOR 4X2":                         "Pickup Truck",
    "CHEVY 1500 4X2":                                "Pickup Truck",
    "CHEVY 1500 CREW CAB":                           "Pickup Truck",
    "CHEVY 1500 CREW CAB 4X4":                       "Pickup Truck",
    "CHEVY 1500 CREW CAB 4x2":                       "Pickup Truck",
    "CHEVY CREW CAB":                                "Pickup Truck",
    "COLORADO CC":                                   "Pickup Truck",
    "DODGE 1500":                                    "Pickup Truck",
    "DODGE 1500 2 DOOR 4X2":                         "Pickup Truck",
    "DODGE 1500 2 DOOR 4X4":                         "Pickup Truck",
    "DODGE 1500 CREW CAB 4X4":                       "Pickup Truck",
    "DODGE 3500 CREW CAB 4X2":                       "Pickup Truck",
    "DODGE CREW CAB":                                "Pickup Truck",
    "DODGE RAM 1/2 TON":                             "Pickup Truck",
    "FORD F150":                                     "Pickup Truck",
    "FORD F150 CREW CAB":                            "Pickup Truck",
    "FORD F150 CREW CAB 4X2":                        "Pickup Truck",
    "FORD F150 CREW CAB 4X4":                        "Pickup Truck",
    "FORD F150 CREW CAB 4x2":                        "Pickup Truck",
    "FORD F350 CREW CAB 4X4":                        "Pickup Truck",
    "GMC 1500 CREW CAB 4X4":                         "Pickup Truck",
    "PICK UP CREW CAB":                              "Pickup Truck",
    "TRUCK PICKUP 3/4 T CREW 4WD GAS":              "Pickup Truck",
    # Pumps
    "PUMP IND 6 DV150IE 75HP SK":                    "Pump",
    "PUMP-2 SUB PUMP-115V 1PH":                      "Pump",
    "Pump High Head 3 HH80C SD TR":                  "Pump",
    "Pump Trash 4 DV100C Electric W/O Panel":        "Pump",
    "Pump Trash 4 DV100C HD 404D22 TR":              "Pump",
    "Pump Trash 6 DV150C SD 4045TF290 CLEAN PRIME":  "Pump",
    # Pump accessories
    "Float Open Green w/ Tyco Lead 50":              "Pump Accessories",
    # Rail car
    "Rail car":                                      "Rail Car",
    # Reach truck
    "4000 REACH":                                    "Reach Truck",
    # Scissor lifts
    "14 Electric scissor lift":                      "Scissor Lift",
    "19 Electric scissor lift":                      "Scissor Lift",
    "19ft ELEC SCISS – SJ3219":                      "Scissor Lift",
    "20 Electric scissor lift":                      "Scissor Lift",
    "26 Electric scissor lift":                      "Scissor Lift",
    "30 Electric scissor lift":                      "Scissor Lift",
    "32 RT Diesel scissor lift":                     "Scissor Lift",
    "3226 Electric scissor lift":                    "Scissor Lift",
    "4732 Electric scissor lift":                    "Scissor Lift",
    "SCISSOR LIFT 26FT 32IN ELEC":                   "Scissor Lift",
    # Scrubbers
    "handheld scrubber":                             "Scrubber",
    "scrubber":                                      "Scrubber",
    "sm riding scubber":                             "Scrubber",
    "walkk behind scrubber":                         "Scrubber",
    "Aqueous Parts Washer - 2412":                   "Washer",
    "Aqueous Parts Washer - 2518":                   "Washer",
    "Aqueous Parts Washer - 2840":                   "Washer",
    "Aqueous Parts Washer - 3648":                   "Washer",
    "Aqueous Parts Washer - 4860":                   "Washer",
    "Aqueous Parts Washer - SJ15":                   "Washer",
    # Semi trucks
    "INTERNATIONAL 561":                             "Semi Truck",
    "LIME TANKER TRUCK Freightliner - FL80":         "Semi Truck",
    "LOWBOY TRACTOR & TRAILER PETE - 367":           "Semi Truck",
    "PETERBILT - 367":                               "Semi Truck",
    # Skid steers
    "226 with attachment":                           "Skid Steer",
    "266 with bucket attachment":                    "Skid Steer",
    "SKID STEER BOBCAT - T590":                      "Skid Steer",
    # Spillguard
    "SPILLGUARD ECONT 10X50X1 A":                    "Spillguard",
    "Spillguard 19x19x3 High Wall HexaPro 40":       "Spillguard",
    # Stake bed trucks
    "12 CC STAKEBED":                                "Stake Bed Truck",
    "12 STAKEBED":                                   "Stake Bed Truck",
    "12 STAKEBED CC":                                "Stake Bed Truck",
    "12 STAKEBED REG CAB":                           "Stake Bed Truck",
    "13 STAKEBED":                                   "Stake Bed Truck",
    "13 STAKEBED CC":                                "Stake Bed Truck",
    "13 STAKEBED REG CAB":                           "Stake Bed Truck",
    "14 STAKEBED CC":                                "Stake Bed Truck",
    "22 STAKEBED":                                   "Stake Bed Truck",
    "9 STAKEBED":                                    "Stake Bed Truck",
    "9 STAKEBED RED CAB 4X2":                        "Stake Bed Truck",
    "STAKE TRUCK CHEVY - 3500 CREW CAB":             "Stake Bed Truck",
    "STAKE TRUCK FORD - F350 4DR CREW CAB":          "Stake Bed Truck",
    "STAKE TRUCK FORD - F350 CREW CAB":              "Stake Bed Truck",
    "STAKE TRUCK FORD - F350 SUPER DUTY CREW CAB":   "Stake Bed Truck",
    "STAKE TRUCK FORD - F550 CREW CAB":              "Stake Bed Truck",
    "12 CC STAKEBED":                                "Stake Bed Truck",
    # Tanks
    "TANK BILEVEL UNCOATED":                         "Tank Standard Steel",
    "TANK ROLL OFF CLOSED":                          "Tank Standard Steel",
    "TANK MIXER COIL 4PDL 10HP":                     "Tank Mixer",
    "TANK-MIXER COIL 4PDL 10HP":                     "Tank Mixer",
    "TANK POLY 4900 OR1000":                         "Tank Poly",
    "TANK POLY 6900":                                "Tank Poly",
    "TANK POLY 6900 OR1000":                         "Tank Poly",
    "4-Yard Debris Box Hopper (additional unit — pit area expansion)": "Tank Standard Steel",
    # Telehandlers
    "12,000 Telehandler":                            "Telehandler",
    "54ft 10K TELE - 10054, DSL, CAB, AC, FF":      "Telehandler",
    "55ft 10K TELE - G10-55A I#-2350":              "Telehandler",
    "TH255":                                         "Telehandler",
    "TL1055":                                        "Telehandler",
    "TL1055 with forks attachment":                  "Telehandler",
    "TL12 SKID W/FRKS":                              "Telehandler",
    "TL122 with forks attachment":                   "Telehandler",
    "TL642":                                         "Telehandler",
    "TL943":                                         "Telehandler",
    "TX1000 MSL with bucket attachment":             "Telehandler",
    "TX1000 with bucket attachment":                 "Telehandler",
    # Tractors
    "HARLAN TUG":                                    "Tractor",
    "TOW TRACTOR JOHN DEERE - 6190R":               "Tractor",
    "TOW TRACTOR JOHN DEERE - 7520":                "Tractor",
    # Track loader
    # Truck Snow
    "TRUCK SNOW PLOW 7-8 FT":                        "Truck Snow",
    "snow box 8":                                    "Truck Snow",
    # UTV
    "UTV, DSL 4x4 - Polaris ProXD4, Cab Heat":      "UTV",
    "UTV, DSL 4x4 - Polaris ProXD4, Cab, Heat":     "UTV",
    # Vans
    "12 PASSENGER VAN":                              "Van",
    "15 PASSENGER VAN":                              "Van",
    "CARGO VAN":                                     "Van",
    "FORD E SERIES CARGO":                           "Van",
    "MINIVAN":                                       "Van",
    "PASSENGER VAN":                                 "Van",
    "TRANSIT CARGO VAN":                             "Van",
    "TRANSIT VAN":                                   "Van",
    # Vehicle attachments
    "CLAM SHELL BUCKET ANVIL ATTACHMENTS":           "Vehicle Attachments",
    "SSL-Pallet Forks":                              "Vehicle Attachments",
    "TH255  Attachment":                             "Vehicle Attachments",
    "TH255 ATTACHMENT":                              "Vehicle Attachments",
    "TL1255 attachment":                             "Vehicle Attachments",
    "TL943 attachment":                              "Vehicle Attachments",
    "74 BUCKET":                                     "Vehicle Attachments",
    # Walkie pallet stackers
    "3,300 LB STACKER":                              "Walkie Pallet Stacker",
    "3,500 LB WALKIE":                               "Walkie Pallet Stacker",
    "3300 WALKIE":                                   "Walkie Pallet Stacker",
    "4000 STACKER":                                  "Walkie Pallet Stacker",
    "4000 Walkie":                                   "Walkie Pallet Stacker",
    "4500 WALKIE":                                   "Walkie Pallet Stacker",
    # Sweepers
    "72 PICK UP BROOM":                              "Sweeper",
    "Lg riding sweeper":                             "Sweeper",
    "walk behind sweeper":                           "Sweeper",
    # Welding equipment
    "Engine-Driven Welder/Generator":                "Welding Equipment",
    "Multi-Process Welder":                          "Welding Equipment",
    "Welder and lead cable kit":                     "Welding Equipment",
    # Corrupted / invalid data → Other
    "10/25/1900 0:00":                               "Other",
    "2/8/1904 0:00":                                 "Other",
    "9/15/1900 0:00":                                "Other",
    "9/18/1900 0:00":                                "Other",
    # Heaters with BTU denominations
    "1.0MIL BTU":                                    "Heater",
    "1.5MIL BTU":                                    "Heater",
    "2.0 Mil BTU":                                   "Heater",
    "3.0MIL BTU":                                    "Heater",
    "400K BTU":                                      "Heater",
    # Pickup trucks — additional variants
    "1 TON CC  4X4":                                 "Pickup Truck",
    "1//2 TON REG CAB":                              "Pickup Truck",
    # Forklifts — additional variants
    "4000 ELEC":                                     "Forklift",
    "6,000 SSR DC":                                  "Forklift",
    "6,500 Pneu LPG":                                "Forklift",
    "7000 Pneu DCFP":                                "Forklift",
    "9,000 LB PNEU DCFP":                           "Forklift",
    # Telehandler — abbreviated spelling
    "6000 TELEHANDLR":                               "Telehandler",
    # Mobile trailers — additional dimensions
    "32X8":                                          "Mobile Trailer",
    "60x64 Complex":                                 "Mobile Trailer",
    # Fittings — additional
    "Adapter 6 Female Cam x FNPT AL":               "Fitting",
    "Adapter 6 Male Cam x FNPT AL":                 "Fitting",
    # Material handler — description equals category name
    "Material Handler":                              "Material Handler",
    # Fire extinguisher / safety accessory
    "OPT-FIREEXT#4411":                              "Other",
}

# ── Keyword fallbacks (checked in order; first match wins) ───────────────────
KEYWORDS: list[tuple[str, str]] = [
    # Keep specific phrases before shorter words they contain
    ("ARTICULATED TRUCK",    "Dump Truck"),
    ("ARTIC TRUCK",          "Dump Truck"),
    ("ARTICULATED BOOM",     "Boom Lift"),
    ("ARTICULATING BOOM",    "Boom Lift"),
    ("STRAIGHT BOOM",        "Boom Lift"),
    ("BOOM LIFT",            "Boom Lift"),
    ("BOOM",                 "Boom Lift"),
    ("SCISSOR LIFT",         "Scissor Lift"),
    ("SCISS",                "Scissor Lift"),
    ("MANLIFT",              "Manlift"),
    ("TELEHANDLR",          "Telehandler"),
    ("TELEHANDLER",          "Telehandler"),
    ("COMPRESSOR",           "Air Compressor & Attachments"),
    ("AIR DRYER",            "Air Dryer"),
    ("DRYER",                "Air Dryer"),
    ("VACUUM TRUCK",         "Box Vacuum"),
    ("BOX VACUUM",           "Box Vacuum"),
    ("CLARIFIER",            "Clarifier"),
    ("COIL TRUCK",           "Coil Truck"),
    ("CRANE",                "Crane"),
    ("DOZER",                "Dozer"),
    ("DRIVE VARIABLE",       "Drive Variable Frequency"),
    ("DUMP TRUCK",           "Dump Truck"),
    ("BACKHOE",              "Excavator"),
    ("EXCAVATOR",            "Excavator"),
    ("FITTING",              "Fitting"),
    ("FLATBED",              "Flatbed Truck"),
    ("GENERATOR",            "Generator"),
    ("GRADER",               "Grader"),
    ("HEATER",               "Heater"),
    ("HOSE",                 "Hose"),
    ("LIGHT TOWER",          "Light Tower"),
    ("TRACK LOADER",         "Track Loader"),
    ("WHEEL LOADER",         "Loader"),
    ("LOADER",               "Loader"),
    ("MINI SKID",            "Mini Skid Steer"),
    ("TEMPORARY STRUCTURE",  "Mobile Trailer"),
    ("OFFICE",               "Mobile Trailer"),
    ("CONNEX",               "Mobile Trailer"),
    ("TRAILER",              "Mobile Trailer"),
    ("PUMP ACCESSORIES",     "Pump Accessories"),
    ("PUMP",                 "Pump"),
    ("REACH TRUCK",          "Reach Truck"),
    ("RAIL CAR",             "Rail Car"),
    ("SCRUBBER",             "Scrubber"),
    ("SCUBBER",              "Scrubber"),
    ("SPECIALTY TRUCK",      "Flatbed Truck"),
    ("SEMI",                 "Semi Truck"),
    ("SKID STEER",           "Skid Steer"),
    ("SPILLGUARD",           "Spillguard"),
    ("STAKE TRUCK",          "Stake Bed Truck"),
    ("STAKEBED",             "Stake Bed Truck"),
    ("TANK MIXER",           "Tank Mixer"),
    ("TANK POLY",            "Tank Poly"),
    ("TANK",                 "Tank Standard Steel"),
    ("SNOW PLOW",            "Truck Snow"),
    ("SNOW BOX",             "Truck Snow"),
    ("UTILITY VEHICLE",      "UTV"),
    ("UTV",                  "UTV"),
    ("VAN",                  "Van"),
    ("FORKLIFT",             "Forklift"),
    ("STACKER",              "Walkie Pallet Stacker"),
    ("WALKIE",               "Walkie Pallet Stacker"),
    ("SWEEPER",              "Sweeper"),
    ("BROOM",                "Sweeper"),
    ("WELDER",               "Welding Equipment"),
    ("WELDING",              "Welding Equipment"),
    ("WASHER",               "Washer"),
    ("LIGHT VEHICLE",        "Pickup Truck"),
    ("PICKUP",               "Pickup Truck"),
    ("PICK UP",              "Pickup Truck"),
    ("GENERATOR",            "Generator"),
    ("ATTACHMENT",           "Vehicle Attachments"),
    ("CART",                 "Cart"),
    ("LEVEL",                "Level Monitoring"),
    ("BTU",                  "Heater"),
]


def classify(description: str) -> str:
    """Return an approved category for the given equipment description."""
    # 1. Exact match
    cat = EXACT.get(description)
    if cat:
        return cat
    # 2. Case-insensitive keyword scan
    upper = description.upper()
    for kw, cat in KEYWORDS:
        if kw in upper:
            return cat
    return "Other"


class Command(BaseCommand):
    help = "Backfill equipment_category on RentalStaging and RentalMaster rows that have a blank category."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without saving.",
        )

    def _process(self, qs, label, dry):
        total = qs.count()
        self.stdout.write(f"{label}: {total} rows to reclassify.")
        updated = 0
        for row in qs.iterator():
            cat = classify(row.equipment_description or "")
            if dry:
                self.stdout.write(f"  [{row.pk}] {row.equipment_description!r} -> {cat}")
            else:
                row.equipment_category = cat
                row.save(update_fields=["equipment_category"])
                updated += 1
        return updated

    def handle(self, *args, **options):
        dry = options["dry_run"]
        from django.db.models import Q
        blank_or_other = Q(equipment_category="") | Q(equipment_category="Other")

        staging_qs = RentalStaging.objects.filter(blank_or_other)
        master_qs  = RentalMaster.objects.filter(blank_or_other)

        s_updated = self._process(staging_qs, "RentalStaging", dry)
        m_updated = self._process(master_qs,  "RentalMaster",  dry)

        if dry:
            self.stdout.write(self.style.WARNING("Dry-run complete — no changes saved."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Updated {s_updated} RentalStaging rows and {m_updated} RentalMaster rows."
                )
            )
