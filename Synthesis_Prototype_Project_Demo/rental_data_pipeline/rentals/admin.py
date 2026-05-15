from django.contrib import admin, messages
from django.utils import timezone
from .models import ApprovedEquipmentCategory, EquipmentMarketRate, PODepartment, RentalMaster, RentalStaging, UserProfile, VendorAudit, VendorCompany


@admin.register(ApprovedEquipmentCategory)
class ApprovedEquipmentCategoryAdmin(admin.ModelAdmin):
	list_display = ("name",)
	search_fields = ("name",)
	ordering = ("name",)

	def has_module_perms(self, request):
		return request.user.is_superuser

	def has_view_permission(self, request, obj=None):
		return request.user.is_superuser

	def has_add_permission(self, request):
		return request.user.is_superuser

	def has_change_permission(self, request, obj=None):
		return request.user.is_superuser

	def has_delete_permission(self, request, obj=None):
		return request.user.is_superuser


def _is_vendor(user):
	profile = getattr(user, "profile", None)
	return bool(profile and profile.role == "vendor")


def _vendor_company_name(user):
	profile = getattr(user, "profile", None)
	if not profile or not profile.company:
		return None
	return profile.company.name


def _can_publish(user):
	if user.is_superuser:
		return True
	profile = getattr(user, "profile", None)
	return bool(profile and profile.can_publish_vendor_data)


@admin.register(RentalStaging)
class RentalStagingAdmin(admin.ModelAdmin):
	actions = ("publish_to_master",)
	list_display = (
		"vendor_name",
		"equipment_id",
		"status",
		"is_validated",
		"submitted_at",
	)
	list_filter = ("status", "is_validated", "currency")
	search_fields = ("vendor_name", "vendor_code", "equipment_id")

	def get_queryset(self, request):
		qs = super().get_queryset(request)
		if request.user.is_superuser:
			return qs
		if _is_vendor(request.user):
			company_name = _vendor_company_name(request.user)
			return qs.filter(vendor_name=company_name) if company_name else qs.none()
		return qs

	def get_readonly_fields(self, request, obj=None):
		if _is_vendor(request.user):
			return (
				"status",
				"is_validated",
				"validation_errors",
				"reviewed_by",
				"reviewed_at",
				"submitted_by",
			)
		return super().get_readonly_fields(request, obj)

	def save_model(self, request, obj, form, change):
		if _is_vendor(request.user):
			obj.vendor_name = _vendor_company_name(request.user) or obj.vendor_name
			if not obj.submitted_by_id:
				obj.submitted_by = request.user
		super().save_model(request, obj, form, change)

	def get_actions(self, request):
		actions = super().get_actions(request)
		if not _can_publish(request.user):
			actions.pop("publish_to_master", None)
		return actions

	@admin.action(description="Publish selected validated rows to rental master")
	def publish_to_master(self, request, queryset):
		if not _can_publish(request.user):
			self.message_user(request, "You do not have publish rights.", level=messages.ERROR)
			return

		published = 0
		skipped = 0
		now = timezone.now()

		for row in queryset:
			if not row.is_validated:
				skipped += 1
				continue

			_, created = RentalMaster.objects.get_or_create(
				approved_from=row,
				defaults={
					"vendor_name": row.vendor_name,
					"vendor_code": row.vendor_code,
					"equipment_id": row.equipment_id,
					"equipment_description": row.equipment_description,
					"quantity": row.quantity,
					"rate_daily": row.rate_daily,
					"currency": row.currency,
					"on_rent_start": row.on_rent_start,
					"on_rent_end": row.on_rent_end,
					"source_file": row.source_file,
					"approved_by": request.user,
					"rvb_candidate": self._check_rvb(row),
				},
			)

			if created:
				published += 1
				row.status = "approved"
				row.reviewed_by = request.user
				row.reviewed_at = now
				row.save(update_fields=["status", "reviewed_by", "reviewed_at"])
			else:
				skipped += 1

		self.message_user(
			request,
			f"Published {published} row(s) to master. Skipped {skipped} row(s).",
		)

	@staticmethod
	def _check_rvb(row):
		"""Return True if the row's monthly cost exceeds the combined ownership +
		maintenance threshold.  rate_daily stores the monthly rental rate.
		Threshold = (purchase_price / (life * 12)) + monthly_maintenance_cost.
		"""
		monthly_cost = row.rate_daily * row.quantity
		rate = (
			EquipmentMarketRate.objects
			.filter(equipment_description__iexact=row.equipment_description)
			.order_by("-effective_date")
			.first()
		)
		if rate is None:
			return False
		# rvb_monthly_threshold already includes monthly_maintenance_cost
		return monthly_cost > rate.rvb_monthly_threshold


@admin.register(RentalMaster)
class RentalMasterAdmin(admin.ModelAdmin):
	list_display = (
		"vendor_name",
		"equipment_id",
		"rate_daily",
		"currency",
		"approved_at",
		"is_active",
		"rvb_candidate",
	)
	list_filter = ("is_active", "currency", "rvb_candidate")
	search_fields = ("vendor_name", "vendor_code", "equipment_id")

	def get_queryset(self, request):
		qs = super().get_queryset(request)
		if request.user.is_superuser:
			return qs
		if _is_vendor(request.user):
			company_name = _vendor_company_name(request.user)
			return qs.filter(vendor_name=company_name) if company_name else qs.none()
		return qs

	def has_add_permission(self, request):
		if _is_vendor(request.user):
			return False
		return super().has_add_permission(request)

	def has_change_permission(self, request, obj=None):
		if _is_vendor(request.user):
			return False
		return super().has_change_permission(request, obj)


@admin.register(VendorAudit)
class VendorAuditAdmin(admin.ModelAdmin):
	actions = ("declare_no_change",)
	list_display = (
		"vendor_name",
		"cadence",
		"cycle_date",
		"verified",
		"no_change",
		"is_late",
		"submitted_at",
		"no_change_declared_at",
	)
	list_filter = ("cadence", "verified", "is_late", "no_change")
	search_fields = ("vendor_name",)

	def get_queryset(self, request):
		qs = super().get_queryset(request)
		if request.user.is_superuser:
			return qs
		if _is_vendor(request.user):
			company_name = _vendor_company_name(request.user)
			return qs.filter(vendor_name=company_name) if company_name else qs.none()
		return qs

	def has_add_permission(self, request):
		if _is_vendor(request.user):
			return False
		return super().has_add_permission(request)

	def has_change_permission(self, request, obj=None):
		if _is_vendor(request.user):
			return False
		return super().has_change_permission(request, obj)

	def get_actions(self, request):
		actions = super().get_actions(request)
		if not _is_vendor(request.user):
			# Only vendors use this action; hide it for admins/superusers
			actions.pop("declare_no_change", None)
		return actions

	@admin.action(description="Declare \u2018No Changes this week\u2019 for selected cycles")
	def declare_no_change(self, request, queryset):
		now = timezone.now()
		updated = 0
		skipped = 0
		for audit in queryset:
			if audit.verified:
				skipped += 1
				continue
			audit.no_change = True
			audit.no_change_declared_at = now
			audit.verified = True
			audit.submitted_at = now
			audit.save(update_fields=["no_change", "no_change_declared_at", "verified", "submitted_at"])
			updated += 1
		self.message_user(
			request,
			f"Declared No Changes for {updated} cycle(s). Skipped {skipped} already-verified cycle(s).",
		)


@admin.register(VendorCompany)
class VendorCompanyAdmin(admin.ModelAdmin):
	list_display = ("name", "slug", "is_active", "created_at")
	list_filter = ("is_active",)
	search_fields = ("name", "slug")


@admin.register(EquipmentMarketRate)
class EquipmentMarketRateAdmin(admin.ModelAdmin):
	list_display = (
		"equipment_description",
		"equipment_category",
		"market_daily_rate",
		"rvb_daily_threshold",
		"estimated_purchase_price",
		"useful_life_years",
		"effective_date",
	)
	list_filter = ("equipment_category",)
	search_fields = ("equipment_description", "equipment_category")
	readonly_fields = ("created_at", "updated_at")
	date_hierarchy = "effective_date"

	def has_view_permission(self, request, obj=None):
		if _is_vendor(request.user):
			return False
		return super().has_view_permission(request, obj)

	def has_change_permission(self, request, obj=None):
		if _is_vendor(request.user):
			return False
		return super().has_change_permission(request, obj)

	def has_add_permission(self, request):
		if _is_vendor(request.user):
			return False
		return super().has_add_permission(request)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = (
		"username",
		"role",
		"company",
		"can_publish_vendor_data",
		"external_user",
		"initial_password",
	)
	list_filter = ("role", "can_publish_vendor_data", "external_user", "company")
	search_fields = ("user__username", "company__name", "initial_password")
	readonly_fields = ("created_at", "updated_at")

	@admin.display(ordering="user__username", description="Username")
	def username(self, obj):
		return obj.user.username


@admin.register(PODepartment)
class PODepartmentAdmin(admin.ModelAdmin):
	list_display = ("po_number", "department")
	list_filter = ("department",)
	search_fields = ("po_number",)
	list_editable = ("department",)
