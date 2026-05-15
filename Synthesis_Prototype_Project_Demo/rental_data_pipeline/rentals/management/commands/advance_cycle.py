"""
Management command: advance_cycle

Creates a new VendorAudit row for every active vendor for the given
week number / cycle date, leaving all submissions as pending (verified=False).

Usage:
    python manage.py advance_cycle              # auto-detects current ISO week
    python manage.py advance_cycle --week 17   # force a specific week number
    python manage.py advance_cycle --date 2026-04-19  # force a specific cycle date
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from rentals.models import UserProfile, UserRole, VendorAudit, VendorCompany

User = get_user_model()


class Command(BaseCommand):
    help = "Open a new weekly audit cycle (pending) for all active vendor companies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--week",
            type=int,
            default=None,
            help="ISO week number to use (e.g. 17). Defaults to current ISO week.",
        )
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Explicit cycle date as YYYY-MM-DD. Overrides --week.",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="ISO year (only used with --week). Defaults to current year.",
        )

    def handle(self, *args, **options):
        # Determine cycle date
        if options["date"]:
            try:
                cycle_date = datetime.date.fromisoformat(options["date"])
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date: {options['date']}. Use YYYY-MM-DD."))
                return
        elif options["week"]:
            year = options["year"] or datetime.date.today().isocalendar()[0]
            week = options["week"]
            # ISO week Monday of that week
            cycle_date = datetime.date.fromisocalendar(year, week, 1)
        else:
            today = datetime.date.today()
            iso = today.isocalendar()
            cycle_date = datetime.date.fromisocalendar(iso[0], iso[1], 1)  # Monday of current week

        self.stdout.write(f"Opening new audit cycle for date: {cycle_date} "
                          f"(ISO week {cycle_date.isocalendar()[1]}, {cycle_date.isocalendar()[0]})")

        # Collect all active vendor companies with their cadences
        vendor_companies = list(VendorCompany.objects.filter(is_active=True).values("name", "cadence"))
        vendor_names = [vc["name"] for vc in vendor_companies]
        cadence_map = {vc["name"]: vc["cadence"] for vc in vendor_companies}

        if not vendor_names:
            # Fallback: derive from UserProfiles with vendor role (cadence defaults to weekly)
            profiles = UserProfile.objects.filter(role=UserRole.VENDOR).select_related("company")
            seen = set()
            for p in profiles:
                name = p.company.name if p.company else None
                if name and name not in seen:
                    vendor_names.append(name)
                    cadence_map[name] = "weekly"
                    seen.add(name)

        if not vendor_names:
            self.stderr.write(self.style.WARNING("No active vendor companies found."))
            return

        created = 0
        skipped = 0
        for name in vendor_names:
            cadence = cadence_map.get(name, "weekly")

            # Monthly vendors get exactly one audit row per calendar month.
            # If one already exists for this month, skip regardless of which
            # week it was originally created in.
            if cadence == "monthly":
                already_this_month = VendorAudit.objects.filter(
                    vendor_name=name,
                    cycle_date__year=cycle_date.year,
                    cycle_date__month=cycle_date.month,
                ).exists()
                if already_this_month:
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ~ Skipped [monthly — already has entry for "
                            f"{cycle_date.year}-{cycle_date.month:02d}]: {name}"
                        )
                    )
                    continue

            obj, was_created = VendorAudit.objects.get_or_create(
                vendor_name=name,
                cycle_date=cycle_date,
                defaults={
                    "cadence": cadence,
                    "verified": False,
                    "no_change": False,
                    "is_late": False,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f"  + Created [{cadence}]: {name}")
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"  ~ Skipped (already exists): {name}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created} cycle(s) created, {skipped} already existed."
        ))
