import csv
import secrets
import string
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from rentals.models import UserProfile, UserRole, VendorCompany, SubmissionCadence


User = get_user_model()

# Vendors whose real-world billing cycle is monthly, not weekly.
MONTHLY_VENDORS = {
    "Christensen, Nixon and Davis",
    "Davidson PLC",
    "Lee-Jordan",
    "Morales, Allen and Jones",
    "Preston LLC",
    "West Inc",
}


class Command(BaseCommand):
    help = (
        "Create user schema data: 2 junior super users and one vendor user per unique "
        "company in dummy CSV."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=str(Path(settings.BASE_DIR).parent / "docs" / "Rental_Report_DUMMY.csv"),
            help="Path to CSV containing RENTAL_COMPANY column.",
        )
        parser.add_argument(
            "--junior-count",
            type=int,
            default=1,
            help="Number of junior super users to create.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"]).resolve()
        junior_count = options["junior_count"]

        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        company_names = self._read_unique_companies(csv_path)
        if not company_names:
            raise CommandError("No companies found in RENTAL_COMPANY column.")

        Group.objects.get_or_create(name="JuniorSuperUser")
        Group.objects.get_or_create(name="Vendor")
        self._sync_group_permissions()

        credentials = []
        self._sync_existing_superusers(credentials)
        self._create_junior_superusers(junior_count, credentials)
        self._create_vendor_users(company_names, credentials)

        self.stdout.write(self.style.SUCCESS("User schema seeded successfully."))
        self.stdout.write("\nCredentials:")
        self.stdout.write("username,password,role,company")
        for row in credentials:
            self.stdout.write(
                f"{row['username']},{row['password']},{row['role']},{row['company']}"
            )

    def _read_unique_companies(self, csv_path: Path):
        companies = set()
        last_error = None
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                with csv_path.open("r", newline="", encoding=encoding) as csv_file:
                    reader = csv.DictReader(csv_file)
                    if "RENTAL_COMPANY" not in (reader.fieldnames or []):
                        raise CommandError(
                            "CSV is missing RENTAL_COMPANY column required for vendor user creation."
                        )

                    for row in reader:
                        name = (row.get("RENTAL_COMPANY") or "").strip()
                        if name:
                            companies.add(name)
                break
            except UnicodeDecodeError as exc:
                last_error = exc

        if last_error and not companies:
            raise CommandError(f"Unable to decode CSV file: {last_error}")

        return sorted(companies)

    def _sync_existing_superusers(self, credentials):
        superusers = User.objects.filter(is_superuser=True).order_by("username")
        for user in superusers:
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "role": UserRole.ADMIN,
                    "can_publish_vendor_data": True,
                    "external_user": False,
                    "initial_password": "EXISTING_PASSWORD",
                },
            )
            profile.role = UserRole.ADMIN
            profile.can_publish_vendor_data = True
            profile.external_user = False
            if not profile.initial_password:
                profile.initial_password = "EXISTING_PASSWORD"
            profile.save(
                update_fields=[
                    "role",
                    "can_publish_vendor_data",
                    "external_user",
                    "initial_password",
                    "updated_at",
                ]
            )

            credentials.append(
                {
                    "username": user.username,
                    "password": profile.initial_password or "EXISTING_PASSWORD",
                    "role": "admin",
                    "company": "-",
                }
            )

    def _sync_group_permissions(self):
        junior_group = Group.objects.get(name="JuniorSuperUser")
        vendor_group = Group.objects.get(name="Vendor")

        junior_codenames = [
            "view_rentalstaging",
            "add_rentalstaging",
            "change_rentalstaging",
            "view_rentalmaster",
            "add_rentalmaster",
            "change_rentalmaster",
            "view_vendoraudit",
            "change_vendoraudit",
        ]
        vendor_codenames = [
            "view_rentalstaging",
            "add_rentalstaging",
            "change_rentalstaging",
            "view_rentalmaster",
            "view_vendoraudit",
        ]

        junior_group.permissions.set(Permission.objects.filter(codename__in=junior_codenames))
        vendor_group.permissions.set(Permission.objects.filter(codename__in=vendor_codenames))

    def _create_junior_superusers(self, junior_count, credentials):
        junior_group = Group.objects.get(name="JuniorSuperUser")

        for idx in range(1, junior_count + 1):
            username = f"junior_super_{idx:02d}"
            password = self._generate_password()

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "is_staff": True,
                    "is_superuser": False,
                    "is_active": True,
                },
            )

            if not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff"])

            if created:
                user.set_password(password)
                user.save(update_fields=["password"])

            user.groups.add(junior_group)

            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "role": UserRole.JUNIOR_SUPERUSER,
                    "can_publish_vendor_data": True,
                    "external_user": False,
                    "initial_password": password if created else "",
                },
            )

            profile.role = UserRole.JUNIOR_SUPERUSER
            profile.can_publish_vendor_data = True
            profile.external_user = False
            if created:
                profile.initial_password = password
            elif not profile.initial_password:
                profile.initial_password = "EXISTING_PASSWORD"
            profile.save(
                update_fields=[
                    "role",
                    "can_publish_vendor_data",
                    "external_user",
                    "initial_password",
                    "updated_at",
                ]
            )

            credentials.append(
                {
                    "username": user.username,
                    "password": profile.initial_password or "EXISTING_PASSWORD",
                    "role": "junior_superuser",
                    "company": "-",
                }
            )

    def _create_vendor_users(self, company_names, credentials):
        vendor_group = Group.objects.get(name="Vendor")

        for company_name in company_names:
            company = self._get_or_create_company(company_name)
            username = self._build_vendor_username(company)
            password = self._generate_password()

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "is_staff": False,
                    "is_superuser": False,
                    "is_active": True,
                },
            )

            if user.is_staff:
                user.is_staff = False
                user.save(update_fields=["is_staff"])

            if created:
                user.set_password(password)
                user.save(update_fields=["password"])

            user.groups.add(vendor_group)

            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "role": UserRole.VENDOR,
                    "company": company,
                    "can_publish_vendor_data": False,
                    "external_user": True,
                    "initial_password": password if created else "",
                },
            )

            profile.role = UserRole.VENDOR
            profile.company = company
            profile.can_publish_vendor_data = False
            profile.external_user = True
            if created:
                profile.initial_password = password
            elif not profile.initial_password:
                profile.initial_password = "EXISTING_PASSWORD"
            profile.save(
                update_fields=[
                    "role",
                    "company",
                    "can_publish_vendor_data",
                    "external_user",
                    "initial_password",
                    "updated_at",
                ]
            )

            credentials.append(
                {
                    "username": user.username,
                    "password": profile.initial_password or "EXISTING_PASSWORD",
                    "role": "vendor",
                    "company": company.name,
                }
            )

    def _get_or_create_company(self, company_name):
        base_slug = slugify(company_name)[:170] or "vendor"
        slug = base_slug
        suffix = 2
        while VendorCompany.objects.exclude(name=company_name).filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"[:180]
            suffix += 1

        cadence = (
            SubmissionCadence.MONTHLY
            if company_name in MONTHLY_VENDORS
            else SubmissionCadence.WEEKLY
        )

        company, created = VendorCompany.objects.get_or_create(
            name=company_name,
            defaults={"slug": slug, "is_active": True, "cadence": cadence},
        )
        # Always correct cadence on pre-existing records so re-runs are idempotent.
        update_fields = ["cadence"]
        if not company.slug:
            company.slug = slug
            update_fields.append("slug")
        if not created:
            company.cadence = cadence
            company.save(update_fields=update_fields)
        elif not company.slug:
            company.slug = slug
            company.save(update_fields=["slug"])
        return company

    def _build_vendor_username(self, company):
        base = f"vendor_{company.slug}".replace("-", "_")
        username = base[:150]
        suffix = 2
        while User.objects.exclude(profile__company=company).filter(username=username).exists():
            extra = f"_{suffix}"
            username = f"{base[:150 - len(extra)]}{extra}"
            suffix += 1
        return username

    def _generate_password(self, length=14):
        alphabet = string.ascii_letters + string.digits + "!@#$%&*?"
        while True:
            password = "".join(secrets.choice(alphabet) for _ in range(length))
            if (
                any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in "!@#$%&*?" for c in password)
            ):
                return password
