"""
Management command: demo_setup

One-shot command that prepares the application for a grading/demo session
regardless of the current calendar week.

What it does (in order):
  0. (--backfill) Detects any gap weeks between the last published RentalMaster
     week and the target week, then fills them by sampling the most recent
     published data pool with a small rate drift — keeping analytics charts
     continuous regardless of when grading occurs.
  1. Auto-detects the current ISO week and year (or accepts --week/--year flags).
  2. Optionally resets the week first (--reset).
  3. Runs advance_cycle for that week if no VendorAudit records exist yet.
  4. Bulk-submits all vendors, leaving one pending for the manual vendor demo
     (default: vendor_smith_llc).  Use --submit-all to mark every vendor complete.
  5. Prints a clear state summary and step-by-step instructions for both the
     Vendor and Reviewer demo flows.

Usage:
    # Standard demo setup — current week, one vendor left pending
    python manage.py demo_setup

    # Reset a previously published/tested week, then re-setup
    python manage.py demo_setup --reset

    # Submit ALL vendors (reviewer sees a fully complete board, nothing to submit)
    python manage.py demo_setup --submit-all

    # Target a specific week (useful if the current week has no staging data)
    python manage.py demo_setup --week 18 --year 2026

    # Override which vendor stays pending
    python manage.py demo_setup --skip vendor_brown_group

    # Fill any gap weeks between the last published week and the current week
    python manage.py demo_setup --backfill

    # Combine — backfill gaps AND reset/prep the current week in one shot
    python manage.py demo_setup --backfill --reset
"""
import datetime
import random
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from rentals.models import (
    RentalMaster,
    RentalStaging,
    SubmissionCadence,
    SubmissionStatus,
    VendorAudit,
    VendorCompany,
)

User = get_user_model()

DEFAULT_SKIP = "vendor_smith_llc"


class Command(BaseCommand):
    help = "One-shot demo/grading setup: opens the current week, bulk-submits vendors, and prints walkthrough instructions."

    def add_arguments(self, parser):
        today = datetime.date.today()
        iso = today.isocalendar()

        parser.add_argument(
            "--week",
            type=int,
            default=iso[1],
            help=f"ISO week number to target (default: current week {iso[1]}).",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=iso[0],
            help=f"ISO year (default: {iso[0]}).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            default=False,
            help="Reset the target week before setting up (wipes published master rows and pending audits).",
        )
        parser.add_argument(
            "--submit-all",
            action="store_true",
            default=False,
            help="Submit ALL vendors — no vendor is left pending. Use for a reviewer-only demo.",
        )
        parser.add_argument(
            "--skip",
            type=str,
            default=DEFAULT_SKIP,
            help=f"Username of the vendor to leave pending for the manual submission demo (default: {DEFAULT_SKIP}).",
        )
        parser.add_argument(
            "--backfill",
            action="store_true",
            default=False,
            help=(
                "Fill any gap weeks between the last published RentalMaster week and "
                "the target week. Uses the most recent published data as a pool, "
                "applies a small rate drift, and publishes directly to master — "
                "keeping analytics charts continuous."
            ),
        )
        parser.add_argument(
            "--no-submit",
            action="store_true",
            default=False,
            help=(
                "Open the cycle but do NOT auto-submit any vendors. "
                "All vendors start as Pending. Use this when you want the reviewer "
                "to see a fully empty board first, then run bulk_submit_vendors manually."
            ),
        )
        parser.add_argument(
            "--full-reset",
            action="store_true",
            default=False,
            help=(
                "Hard-wipe ALL staging, master, and audit rows for the target week, "
                "then re-open the cycle. Combine with --skip or --no-submit to control "
                "submission state after the wipe."
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # Vendors whose real-world billing cycle is monthly, not weekly.
    _MONTHLY_VENDORS = {
        "Christensen, Nixon and Davis",
        "Davidson PLC",
        "Lee-Jordan",
        "Morales, Allen and Jones",
        "Preston LLC",
        "West Inc",
    }

    def _fix_vendor_cadences(self):
        """Ensure VendorCompany cadence fields match the intended real-world schedule.

        This is idempotent — safe to call on every demo_setup run so that any
        pre-existing DB seeded before this fix is automatically corrected.
        Also corrects cadence on existing VendorAudit rows so the review
        dashboard KPIs (NOT REQUIRED counter) reflect the right cadence.
        """
        for company in VendorCompany.objects.all():
            expected = (
                SubmissionCadence.MONTHLY
                if company.name in self._MONTHLY_VENDORS
                else SubmissionCadence.WEEKLY
            )
            if company.cadence != expected:
                company.cadence = expected
                company.save(update_fields=["cadence"])
                self.stdout.write(
                    f"  [cadence] Fixed VendorCompany {company.name!r}: weekly → monthly"
                )

        # Correct cadence on existing VendorAudit rows (snapshot field set at
        # row-creation time — must be patched separately from VendorCompany).
        monthly_fixed = VendorAudit.objects.filter(
            vendor_name__in=self._MONTHLY_VENDORS
        ).exclude(cadence=SubmissionCadence.MONTHLY).update(
            cadence=SubmissionCadence.MONTHLY
        )
        weekly_fixed = VendorAudit.objects.exclude(
            vendor_name__in=self._MONTHLY_VENDORS
        ).exclude(cadence=SubmissionCadence.WEEKLY).update(
            cadence=SubmissionCadence.WEEKLY
        )
        if monthly_fixed or weekly_fixed:
            self.stdout.write(
                f"  [cadence] Corrected {monthly_fixed} monthly + "
                f"{weekly_fixed} weekly VendorAudit row(s)."
            )

    def _backfill_gap_weeks(self, target_week, target_year):
        """
        Detect any unpublished weeks between the last published RentalMaster
        week and target_week, then fill them by sampling the most recent
        published pool with a light rate drift.  Each gap week gets:
          - RentalStaging rows (status=APPROVED)
          - RentalMaster rows (published, is_active=True)
          - VendorAudit rows (all verified; 0–2 random vendors marked late)
        """
        # Find the most recent published week before the target
        last = (
            RentalMaster.objects
            .filter(cycle_year=target_year)
            .exclude(cycle_week__gte=target_week)
            .order_by("-cycle_week")
            .values("cycle_week", "cycle_year")
            .first()
        )

        if not last:
            self.stdout.write(
                self.style.WARNING(
                    "  [backfill] No published master rows found for this year — nothing to backfill from."
                )
            )
            return

        last_week = last["cycle_week"]
        last_year = last["cycle_year"]

        gap_weeks = list(range(last_week + 1, target_week))
        if not gap_weeks:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [backfill] No gap — last published week is W{last_week}. Nothing to fill."
                )
            )
            return

        self.stdout.write(
            f"  [backfill] Last published week: W{last_week}. "
            f"Gap week(s) to fill: {gap_weeks}"
        )

        # Use the most recent published week's master rows as the pool
        pool = list(
            RentalMaster.objects
            .filter(cycle_week=last_week, cycle_year=last_year)
            .values(
                "vendor_name", "vendor_code", "equipment_id",
                "equipment_description", "quantity", "rate_daily",
                "currency", "on_rent_start", "on_rent_end",
                "po_number", "sn_request_number", "equipment_category",
            )
        )

        if not pool:
            self.stdout.write(
                self.style.WARNING(
                    f"  [backfill] W{last_week} has no master rows to sample from — aborting backfill."
                )
            )
            return

        approver = User.objects.filter(is_superuser=True).first() or User.objects.first()
        # Deterministic seed so repeated runs produce the same data
        rng = random.Random(target_week * 1000 + target_year)
        all_vendors = sorted({r["vendor_name"] for r in pool})
        chronic_late = rng.sample(all_vendors, k=min(2, len(all_vendors)))

        with transaction.atomic():
            for week in gap_weeks:
                monday = datetime.date.fromisocalendar(target_year, week, 1)

                # Skip if already published (idempotent)
                if RentalMaster.objects.filter(cycle_week=week, cycle_year=target_year).exists():
                    self.stdout.write(
                        self.style.WARNING(f"    W{week}: already published — skipped.")
                    )
                    continue

                # Use existing staging rows for this week if they are already there
                # (avoids duplicating rows that bulk_submit_vendors already created).
                existing = list(
                    RentalStaging.objects.filter(cycle_week=week, cycle_year=target_year)
                )
                if existing:
                    created_staging = existing
                    self.stdout.write(
                        f"    W{week}: using {len(existing)} existing staging row(s)."
                    )
                else:
                    # Build rows: copy pool with small rate drift (3% of rows ±2%)
                    week_rows = []
                    for r in pool:
                        rate = r["rate_daily"]
                        if rng.random() < 0.03:
                            factor = Decimal(str(round(rng.uniform(0.98, 1.02), 4)))
                            rate = (rate * factor).quantize(
                                Decimal("0.01"), rounding=ROUND_HALF_UP
                            )
                        week_rows.append({**r, "rate_daily": rate})

                    staging_objs = [
                        RentalStaging(
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
                            equipment_category=r["equipment_category"],
                            cycle_week=week,
                            cycle_year=target_year,
                            source_file=f"backfill_wk{week}_{target_year}",
                            status=SubmissionStatus.APPROVED,
                            is_validated=True,
                        )
                        for r in week_rows
                    ]
                    created_staging = RentalStaging.objects.bulk_create(staging_objs)

                # Master
                RentalMaster.objects.bulk_create([
                    RentalMaster(
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
                        equipment_category=s.equipment_category,
                        cycle_week=week,
                        cycle_year=target_year,
                        source_file=s.source_file,
                        approved_from=s,
                        approved_by=approver,
                        is_active=True,
                    )
                    for s in created_staging
                ])

                # VendorAudit — 0-2 random vendors marked late
                n_late = rng.randint(0, 2)
                late_vendors = set(
                    rng.sample(chronic_late, k=min(n_late, len(chronic_late)))
                )
                for vendor in all_vendors:
                    is_late = vendor in late_vendors
                    submitted_day = monday + datetime.timedelta(days=rng.randint(0, 3))
                    VendorAudit.objects.get_or_create(
                        vendor_name=vendor,
                        cycle_date=monday,
                        defaults={
                            "verified": not is_late,
                            "is_late": is_late,
                            "submitted_at": timezone.make_aware(
                                datetime.datetime.combine(
                                    submitted_day,
                                    datetime.time(
                                        rng.randint(7, 17), rng.randint(0, 59)
                                    ),
                                )
                            ) if not is_late else None,
                            "notes": (
                                "Late submission — backfilled."
                                if is_late
                                else f"Week {week} data submitted on time (backfilled)."
                            ),
                        },
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"    W{week} ({monday}): {len(created_staging)} rows published."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"  [backfill] Done — {len(gap_weeks)} gap week(s) filled."
            )
        )

    def _separator(self):
        self.stdout.write("─" * 60)

    def _section(self, title):
        self._separator()
        self.stdout.write(self.style.HTTP_INFO(f"  {title}"))
        self._separator()

    def _state_summary(self, week, year, cycle_date, skip_username, submit_all):
        """Print a readable state snapshot of the target week."""
        audits = VendorAudit.objects.filter(cycle_date=cycle_date)
        total = audits.count()
        submitted = audits.filter(verified=True).count()
        pending = audits.filter(verified=False).count()
        published = RentalMaster.objects.filter(cycle_week=week, cycle_year=year).exists()

        self._section(f"State Snapshot — Week {week}, {year}  (cycle date: {cycle_date})")
        self.stdout.write(f"  Vendors registered : {total}")
        self.stdout.write(
            self.style.SUCCESS(f"  Submitted          : {submitted}")
            if submitted
            else f"  Submitted          : {submitted}"
        )
        self.stdout.write(
            self.style.WARNING(f"  Pending            : {pending}")
            if pending
            else self.style.SUCCESS(f"  Pending            : {pending}")
        )
        self.stdout.write(
            self.style.SUCCESS("  Week published     : YES")
            if published
            else self.style.WARNING("  Week published     : NO  (ready for review)")
        )
        self._separator()

        # List pending vendors
        if pending:
            self.stdout.write(self.style.WARNING("  Pending vendor(s):"))
            for a in audits.filter(verified=False):
                self.stdout.write(f"    • {a.vendor_name}")
            self._separator()

    def _print_walkthrough(self, week, year, skip_username, submit_all):
        """Print step-by-step demo instructions for both user roles."""

        # Resolve pending vendor's display name for the instructions
        pending_label = skip_username
        try:
            u = User.objects.get(username=skip_username)
            profile = getattr(u, "profile", None)
            if profile and profile.company:
                pending_label = f"{profile.company.name}  (login: {skip_username})"
        except User.DoesNotExist:
            pass

        self._section("Demo Walkthrough Instructions")

        if not submit_all:
            self.stdout.write(self.style.HTTP_INFO(f"  ── VENDOR FLOW (submit as {skip_username}) ──"))
            self.stdout.write("")
            self.stdout.write("  1. Open http://127.0.0.1:8000/login/")
            self.stdout.write(f"     Username : {skip_username}")
            self.stdout.write("     Password : fDTyJhaF7NWD$%")
            self.stdout.write("     2FA code : 111111")
            self.stdout.write("")
            self.stdout.write("  2. You land on /vendor/ — the Vendor Dashboard.")
            self.stdout.write("     The equipment table shows this vendor's rental rows.")
            self.stdout.write("     Any row can be edited inline (pencil icon).")
            self.stdout.write("")
            self.stdout.write("  3. Click  [Submit Week's Data]  to submit.")
            self.stdout.write("     The button is replaced by a green 'Submitted' badge.")
            self.stdout.write("     The submission window stays open until the Junior Super")
            self.stdout.write("     User publishes — vendors can re-edit until then.")
            self.stdout.write("")
            self.stdout.write("  4. Log out via the top-right menu.")
            self.stdout.write("")

        self.stdout.write(self.style.HTTP_INFO("  ── REVIEWER FLOW (junior_super_01) ──"))
        self.stdout.write("")
        self.stdout.write("  1. Open http://127.0.0.1:8000/login/")
        self.stdout.write("     Username : junior_super_01")
        self.stdout.write("     Password : 651&JaWrLFkD@X")
        self.stdout.write("     2FA code : 111111")
        self.stdout.write("")
        self.stdout.write("  2. You land on /review/ — the Weekly Review dashboard.")
        self.stdout.write(f"     Week {week}/{year} is shown with all vendor submission statuses.")
        if not submit_all:
            self.stdout.write(f"     {pending_label} will show Pending")
            self.stdout.write("     until the vendor submits (step 3 above).")
        self.stdout.write("")
        self.stdout.write("  3. Once all vendors show Submitted, the")
        self.stdout.write("     [Publish to Master Ledger] button activates.")
        self.stdout.write("     Click it to promote staging rows → master ledger.")
        self.stdout.write("")
        self.stdout.write("  4. After publishing, visit /analytics/ to see the")
        self.stdout.write("     updated charts (Cost Over Time, Week Comparison,")
        self.stdout.write("     Vendor Compliance, Rent-vs-Buy flags).")
        self.stdout.write("")

        self.stdout.write(self.style.HTTP_INFO("  ── RESET & REPEAT ──"))
        self.stdout.write("")
        self.stdout.write("  Wipe master + re-open (staging rows preserved):")
        self.stdout.write(f"    python manage.py demo_setup --reset --week {week} --year {year}")
        self.stdout.write("")
        self.stdout.write("  Hard-wipe everything — all 25 vendors back to Pending:")
        self.stdout.write(f"    python manage.py demo_setup --full-reset --week {week} --year {year}")
        self.stdout.write("")
        self.stdout.write("  Fully submit ALL vendors (reviewer-only demo):")
        self.stdout.write(f"    python manage.py demo_setup --submit-all --week {week} --year {year}")
        self._separator()

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        week = options["week"]
        year = options["year"]
        do_reset = options["reset"]
        full_reset = options["full_reset"]
        submit_all = options["submit_all"]
        skip_username = options["skip"]
        do_backfill = options["backfill"]
        no_submit = options["no_submit"]

        try:
            cycle_date = datetime.date.fromisocalendar(year, week, 1)
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(f"Invalid week/year: {exc}"))
            return

        self._section(f"demo_setup — Week {week}, {year}  ({cycle_date})")

        # ── Step 0a: ensure VendorCompany cadences are correct ──────────
        self._fix_vendor_cadences()

        # ── Step 0: optional gap backfill ───────────────────────────────
        if do_backfill:
            self.stdout.write("  Checking for gap weeks to backfill …")
            self._backfill_gap_weeks(week, year)

        # ── Step 1a: full-reset — hard-wipe staging + master + audits ───
        if full_reset:
            self.stdout.write(self.style.WARNING("  --full-reset: wiping all staging, master, and audit rows …"))
            with transaction.atomic():
                ds, _ = RentalStaging.objects.filter(cycle_week=week, cycle_year=year).delete()
                dm, _ = RentalMaster.objects.filter(cycle_week=week, cycle_year=year).delete()
                da, _ = VendorAudit.objects.filter(cycle_date=cycle_date).delete()
            self.stdout.write(f"  Wiped: {ds} staging, {dm} master, {da} audit rows.")

        # ── Step 1b: standard reset (master + audit only, staging preserved) ──
        elif do_reset:
            self.stdout.write(self.style.WARNING("  Resetting week …"))
            call_command(
                "reset_week",
                week=week,
                year=year,
                stdout=self.stdout,
                stderr=self.stderr,
            )

        # ── Step 2: advance_cycle ────────────────────────────────────────
        # Always run after --reset (rows exist but may be incomplete — 
        # advance_cycle uses get_or_create so it only adds missing vendors).
        # Also run when no rows exist at all.
        existing_audits = VendorAudit.objects.filter(cycle_date=cycle_date).count()
        if existing_audits == 0 or do_reset or full_reset:
            if existing_audits == 0:
                self.stdout.write(
                    f"  No VendorAudit records found for Week {week} — opening cycle …"
                )
            else:
                self.stdout.write(
                    f"  Post-reset: ensuring all vendors have audit rows for Week {week} …"
                )
            call_command(
                "advance_cycle",
                week=week,
                year=year,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Week {week} already open ({existing_audits} audit record(s) found)."
                )
            )

        # ── Step 3: bulk-submit vendors ─────────────────────────────────
        if no_submit:
            self.stdout.write(
                self.style.WARNING(
                    "  --no-submit: skipping bulk submission. All vendors are Pending."
                )
            )
        elif submit_all:
            self.stdout.write("  Submitting ALL vendors (--submit-all) …")
            # Call bulk_submit_vendors with a non-existent skip so nothing is skipped
            call_command(
                "bulk_submit_vendors",
                week=week,
                year=year,
                skip="__none__",
                stdout=self.stdout,
                stderr=self.stderr,
            )
        else:
            self.stdout.write(
                f"  Bulk-submitting vendors, leaving '{skip_username}' pending …"
            )
            call_command(
                "bulk_submit_vendors",
                week=week,
                year=year,
                skip=skip_username,
                stdout=self.stdout,
                stderr=self.stderr,
            )

        # ── Step 4: state snapshot ──────────────────────────────────────
        self._state_summary(week, year, cycle_date, skip_username, submit_all)

        # ── Step 5: walkthrough instructions ───────────────────────────
        self._print_walkthrough(week, year, skip_username, submit_all)

        self.stdout.write(
            self.style.SUCCESS("  demo_setup complete. Application is ready for review.")
        )
        self._separator()
