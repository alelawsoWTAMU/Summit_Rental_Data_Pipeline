"""
Management command: bulk_submit_vendors

Marks all vendor VendorAudit records for the current week as verified/submitted
(as-is, with no_change=False), except for the designated test vendor account
(default: vendor_smith_llc) which is left pending so it can be submitted manually.

Staging rows for each submitted vendor are also stamped with the current
cycle week/year so they appear in the weekly review table.

Usage:
    python manage.py bulk_submit_vendors                        # skips vendor_smith_llc
    python manage.py bulk_submit_vendors --skip vendor_brown_group
    python manage.py bulk_submit_vendors --week 18 --year 2026
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from rentals.models import RentalMaster, RentalStaging, SubmissionStatus, VendorAudit
from django.contrib.auth import get_user_model

User = get_user_model()

DEFAULT_SKIP_USERNAME = "vendor_smith_llc"


class Command(BaseCommand):
    help = "Mark all vendor submissions for the current week as complete, except the test vendor."

    def add_arguments(self, parser):
        today = datetime.date.today()
        iso = today.isocalendar()
        parser.add_argument(
            "--week",
            type=int,
            default=iso[1],
            help=f"ISO week number (default: current week {iso[1]}).",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=iso[0],
            help=f"ISO year (default: {iso[0]}).",
        )
        parser.add_argument(
            "--skip",
            type=str,
            default=DEFAULT_SKIP_USERNAME,
            help=(
                f"Username of the vendor to leave pending for manual testing "
                f"(default: {DEFAULT_SKIP_USERNAME})."
            ),
        )

    def handle(self, *args, **options):
        week = options["week"]
        year = options["year"]
        skip_username = options["skip"]

        try:
            cycle_date = datetime.date.fromisocalendar(year, week, 1)
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(f"Invalid week/year: {exc}"))
            return

        # Resolve the company name to skip from the username.
        # '__none__' is an internal sentinel used by demo_setup --submit-all;
        # skip silently so the output stays clean.
        skip_company = None
        if skip_username and skip_username != "__none__":
            try:
                skip_user = User.objects.get(username=skip_username)
                profile = getattr(skip_user, "profile", None)
                if profile and profile.company:
                    skip_company = profile.company.name
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"  User '{skip_username}' not found — no vendor will be skipped."
                    )
                )

        self.stdout.write(
            f"Bulk-submitting vendors for Week {week}, {year} (cycle date: {cycle_date}) …"
        )
        if skip_company:
            self.stdout.write(f"  Skipping: {skip_company} ({skip_username})")

        audits = VendorAudit.objects.filter(cycle_date=cycle_date, verified=False)
        if skip_company:
            audits = audits.exclude(vendor_name=skip_company)

        submitted = 0
        now = timezone.now()

        for audit in audits:
            audit.verified = True
            audit.no_change = False
            audit.submitted_at = now
            audit.notes = "Bulk-submitted via bulk_submit_vendors management command."
            audit.save(update_fields=["verified", "no_change", "submitted_at", "notes", "updated_at"])

            # Ensure *submitted* staging rows exist for this specific cycle week.
            # A vendor may have uploaded pending rows via the portal without submitting;
            # those are not sufficient — we need submitted rows in the table.
            if not RentalStaging.objects.filter(
                vendor_name=audit.vendor_name,
                cycle_week=week,
                cycle_year=year,
                status=SubmissionStatus.SUBMITTED,
            ).exists():
                # Seed from the vendor's most recent published master rows.
                ref = (
                    RentalMaster.objects
                    .filter(vendor_name=audit.vendor_name, is_active=True)
                    .order_by("-cycle_year", "-cycle_week")
                    .values("cycle_week", "cycle_year")
                    .first()
                )
                if ref:
                    prior = list(
                        RentalMaster.objects.filter(
                            vendor_name=audit.vendor_name,
                            is_active=True,
                            cycle_week=ref["cycle_week"],
                            cycle_year=ref["cycle_year"],
                        )
                    )
                    if prior:
                        RentalStaging.objects.bulk_create([
                            RentalStaging(
                                vendor_name=m.vendor_name,
                                vendor_code=m.vendor_code,
                                equipment_id=m.equipment_id,
                                equipment_description=m.equipment_description,
                                equipment_category=m.equipment_category,
                                quantity=m.quantity,
                                rate_daily=m.rate_daily,
                                currency=m.currency,
                                on_rent_start=m.on_rent_start,
                                on_rent_end=m.on_rent_end,
                                po_number=m.po_number,
                                sn_request_number=m.sn_request_number,
                                cycle_week=week,
                                cycle_year=year,
                                source_file=f"bulk_submit_wk{week}_{year}",
                                status=SubmissionStatus.SUBMITTED,
                                is_validated=True,
                            )
                            for m in prior
                        ])

            self.stdout.write(f"  ✓ {audit.vendor_name}")
            submitted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {submitted} vendor(s) marked as submitted."
            )
        )
        if skip_company:
            self.stdout.write(
                f"  '{skip_company}' ({skip_username}) left pending for manual testing."
            )
