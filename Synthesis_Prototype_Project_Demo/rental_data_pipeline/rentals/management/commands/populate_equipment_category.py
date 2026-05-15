"""
Management command: populate_equipment_category

Populates the equipment_category field on RentalMaster rows by looking up
each equipment_description in EquipmentMarketRate. Uses the latest (most recent)
effective_date for each description.

Usage:
    python manage.py populate_equipment_category
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from rentals.models import EquipmentMarketRate, RentalMaster


class Command(BaseCommand):
    help = "Populate equipment_category on RentalMaster rows from EquipmentMarketRate."

    def handle(self, *args, **options):
        # Get all unique equipment descriptions in RentalMaster
        descriptions = set(
            RentalMaster.objects.exclude(equipment_description="")
            .values_list("equipment_description", flat=True)
            .distinct()
        )

        # Build a lookup dict: description → category
        lookup = {}
        for desc in descriptions:
            # Get the most recent (effective_date) market rate for this description
            mkt = (
                EquipmentMarketRate.objects.filter(
                    equipment_description__iexact=desc
                )
                .order_by("-effective_date")
                .first()
            )
            if mkt and mkt.equipment_category:
                lookup[desc] = mkt.equipment_category

        self.stdout.write(
            self.style.SUCCESS(
                f"Found categories for {len(lookup)} of {len(descriptions)} equipment descriptions."
            )
        )

        # Batch update RentalMaster rows
        updated = 0
        for desc, category in lookup.items():
            n = RentalMaster.objects.filter(equipment_description=desc).update(
                equipment_category=category
            )
            updated += n

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated} RentalMaster rows with equipment category."
            )
        )
