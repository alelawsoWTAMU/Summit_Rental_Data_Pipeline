from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class LoginOTP(models.Model):
    """
    Single-use 6-digit OTP issued at login for email-based 2-factor authentication.
    Expires after OTP_EXPIRY_MINUTES minutes and is invalidated after first use.
    """
    OTP_EXPIRY_MINUTES = 10

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_otps")
    code       = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def is_valid(self):
        """True if not yet used and not yet expired."""
        from django.utils import timezone
        import datetime
        age = timezone.now() - self.created_at
        return not self.is_used and age < datetime.timedelta(minutes=self.OTP_EXPIRY_MINUTES)

    def __str__(self):
        return f"OTP for {self.user} ({'used' if self.is_used else 'active'})"


class SubmissionCadence(models.TextChoices):
	WEEKLY = "weekly", "Weekly"
	MONTHLY = "monthly", "Monthly"


class SubmissionStatus(models.TextChoices):
	PENDING = "pending", "Pending"
	SUBMITTED = "submitted", "Submitted"
	APPROVED = "approved", "Approved"
	REJECTED = "rejected", "Rejected"


class UserRole(models.TextChoices):
	ADMIN = "admin", "Administrator"
	JUNIOR_SUPERUSER = "junior_superuser", "Junior Super User"
	VENDOR = "vendor", "Vendor"


class ApprovedEquipmentCategory(models.Model):
	"""Admin-managed list of approved equipment categories."""
	name = models.CharField(max_length=120, unique=True)

	class Meta:
		ordering = ["name"]
		verbose_name = "Approved Equipment Category"
		verbose_name_plural = "Approved Equipment Categories"

	def __str__(self):
		return self.name


class RentalRecordBase(models.Model):
	vendor_name = models.CharField(max_length=120)
	vendor_code = models.CharField(max_length=50, blank=True)
	equipment_id = models.CharField(max_length=80)
	equipment_description = models.CharField(max_length=255)
	quantity = models.PositiveIntegerField(default=1)
	rate_daily = models.DecimalField(max_digits=12, decimal_places=2)
	currency = models.CharField(max_length=3, default="USD")
	on_rent_start = models.DateField()
	on_rent_end = models.DateField(null=True, blank=True)
	po_number = models.CharField(max_length=80, blank=True)
	sn_request_number = models.CharField(max_length=80, blank=True)
	comments = models.TextField(blank=True)
	cycle_week = models.PositiveIntegerField(null=True, blank=True)
	cycle_year = models.PositiveIntegerField(null=True, blank=True)
	source_file = models.CharField(max_length=255, blank=True)
	uploaded_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		abstract = True

	def __str__(self):
		return f"{self.vendor_name} | {self.equipment_id}"


class RentalStaging(RentalRecordBase):
	submitted_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="staging_submissions",
	)
	submitted_at = models.DateTimeField(auto_now_add=True)
	status = models.CharField(
		max_length=20,
		choices=SubmissionStatus.choices,
		default=SubmissionStatus.PENDING,
	)
	is_validated = models.BooleanField(default=False)
	validation_errors = models.TextField(blank=True)
	equipment_category = models.CharField(max_length=120, blank=True)
	reviewed_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="staging_reviews",
	)
	reviewed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ["-submitted_at"]


class RentalMaster(RentalRecordBase):
	approved_from = models.ForeignKey(
		RentalStaging,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="published_rows",
	)
	approved_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="master_approvals",
	)
	approved_at = models.DateTimeField(auto_now_add=True)
	is_active = models.BooleanField(default=True)
	rvb_candidate = models.BooleanField(
		default=False,
		help_text="Flagged as a rent-vs-buy candidate based on market rate comparison.",
	)
	equipment_category = models.CharField(
		max_length=120,
		blank=True,
		help_text="Equipment category (e.g., Wheel Loader, Light Tower) from EquipmentMarketRate.",
	)

	class Meta:
		ordering = ["-approved_at"]


class VendorAudit(models.Model):
	vendor_name = models.CharField(max_length=120)
	vendor_user = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="vendor_audits",
	)
	cadence = models.CharField(
		max_length=20,
		choices=SubmissionCadence.choices,
		default=SubmissionCadence.WEEKLY,
	)
	cycle_date = models.DateField(help_text="Cycle anchor date for weekly/monthly compliance")
	logged_in_at = models.DateTimeField(null=True, blank=True)
	submitted_at = models.DateTimeField(null=True, blank=True)
	no_change = models.BooleanField(
		default=False,
		help_text="Vendor explicitly declared no changes for this cycle.",
	)
	no_change_declared_at = models.DateTimeField(
		null=True,
		blank=True,
		help_text="Timestamp when vendor submitted the No Changes declaration.",
	)
	verified = models.BooleanField(default=False)
	is_late = models.BooleanField(default=False)
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-cycle_date", "vendor_name"]
		unique_together = ("vendor_name", "cycle_date")

	def __str__(self):
		return f"{self.vendor_name} ({self.cycle_date})"


class VendorCompany(models.Model):
	name = models.CharField(max_length=160, unique=True)
	slug = models.SlugField(max_length=180, unique=True)
	cadence = models.CharField(
		max_length=20,
		choices=SubmissionCadence.choices,
		default=SubmissionCadence.WEEKLY,
		help_text="Expected submission frequency for this vendor.",
	)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]

	def __str__(self):
		return self.name


class EquipmentMarketRate(models.Model):
	"""Reference table for rent-vs-buy threshold calculations."""

	equipment_description = models.CharField(
		max_length=255,
		help_text="Equipment type label matching rental_master equipment_description.",
	)
	equipment_category = models.CharField(max_length=120, blank=True)
	estimated_purchase_price = models.DecimalField(
		max_digits=14,
		decimal_places=2,
		help_text="Estimated purchase price (USD) for this equipment type.",
	)
	useful_life_years = models.PositiveSmallIntegerField(
		default=5,
		help_text="Expected useful life in years for straight-line cost comparison.",
	)
	market_daily_rate = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		help_text="Current market daily rental rate benchmark (USD).",
	)
	rvb_daily_threshold = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		help_text="Daily cost above which renting exceeds straight-line ownership cost.",
	)
	rvb_monthly_threshold = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		help_text="Monthly cost above which renting exceeds straight-line ownership cost (purchase_price / useful_life_years / 12).",
	)
	annual_maintenance_pct = models.DecimalField(
		max_digits=5,
		decimal_places=4,
		default=0,
		help_text="Estimated annual maintenance cost as a fraction of purchase price (e.g. 0.12 = 12%).",
	)
	monthly_maintenance_cost = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		default=0,
		help_text="Estimated monthly maintenance cost = purchase_price × annual_maintenance_pct / 12.",
	)
	effective_date = models.DateField(help_text="Date this rate record became effective.")
	source_notes = models.TextField(blank=True, help_text="Rate source or reference.")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["equipment_description", "-effective_date"]
		indexes = [models.Index(fields=["equipment_description"])]

	def __str__(self):
		return f"{self.equipment_description} (threshold: ${self.rvb_daily_threshold}/day)"


class UserProfile(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
	role = models.CharField(max_length=32, choices=UserRole.choices)
	company = models.ForeignKey(
		VendorCompany,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="users",
	)
	can_publish_vendor_data = models.BooleanField(default=False)
	external_user = models.BooleanField(
		default=False,
		help_text="Flag for third-party/vendor users outside internal operations roles.",
	)
	# Dev-only seed password visibility for admin. Do not use plaintext storage in production.
	initial_password = models.CharField(max_length=128, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["role", "user__username"]

	def __str__(self):
		return f"{self.user.username} ({self.get_role_display()})"


class MillDepartment(models.TextChoices):
	COKE     = "Coke",     "Coke"
	IRON     = "Iron",     "Iron"
	STEEL    = "Steel",    "Steel"
	PLATE    = "Plate",    "Plate"
	HOT_MILL = "Hot Mill", "Hot Mill"
	COLD_MILL = "Cold Mill", "Cold Mill"
	MEU      = "MEU",      "MEU"


class PODepartment(models.Model):
	"""Maps a PO number to a steel mill department."""
	po_number  = models.CharField(max_length=80, unique=True)
	department = models.CharField(
		max_length=20,
		choices=MillDepartment.choices,
		default=MillDepartment.COKE,
	)

	class Meta:
		ordering = ["po_number"]
		verbose_name = "PO Department"
		verbose_name_plural = "PO Departments"

	def __str__(self):
		return f"{self.po_number} → {self.department}"

