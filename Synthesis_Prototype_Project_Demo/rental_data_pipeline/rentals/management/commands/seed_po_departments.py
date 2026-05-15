"""
Management command: seed_po_departments

Assigns every distinct PO number in RentalMaster to one of the seven
steel mill departments at random.  Existing assignments are left untouched
so re-running the command is idempotent (only NEW POs get assigned).

Usage:
    python manage.py seed_po_departments
    python manage.py seed_po_departments --reset   # re-randomise everything
"""

import random

from django.core.management.base import BaseCommand

from rentals.models import MillDepartment, PODepartment, RentalMaster

DEPARTMENTS = [d.value for d in MillDepartment]


class Command(BaseCommand):
    help = "Randomly assign every PO number to a steel mill department."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing assignments before re-seeding.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = PODepartment.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing assignments."))

        # All distinct, non-blank PO numbers across the entire master table
        all_pos = set(
            RentalMaster.objects.exclude(po_number="")
            .values_list("po_number", flat=True)
            .distinct()
        )

        # POs that already have an assignment
        existing = set(PODepartment.objects.values_list("po_number", flat=True))

        to_create = [
            PODepartment(po_number=po, department=random.choice(DEPARTMENTS))
            for po in sorted(all_pos - existing)
        ]

        PODepartment.objects.bulk_create(to_create, batch_size=500)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(to_create)} new PO→department assignments "
                f"({len(existing)} already existed, {len(all_pos)} total POs)."
            )
        )
