from django.conf import settings
from django.db import migrations, models


INTERNAL_ROLES = {"admin", "junior_superuser"}


def sync_external_and_staff(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    UserProfile = apps.get_model("rentals", "UserProfile")

    for profile in UserProfile.objects.select_related("user").all():
        role = profile.role
        is_external = role not in INTERNAL_ROLES

        if profile.external_user != is_external:
            profile.external_user = is_external
            profile.save(update_fields=["external_user"])

        user = profile.user
        should_staff = role in INTERNAL_ROLES
        if user.is_staff != should_staff:
            user.is_staff = should_staff
            user.save(update_fields=["is_staff"])


class Migration(migrations.Migration):

    dependencies = [
        ("rentals", "0008_comments_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="external_user",
            field=models.BooleanField(
                default=False,
                help_text="Flag for third-party/vendor users outside internal operations roles.",
            ),
        ),
        migrations.RunPython(sync_external_and_staff, migrations.RunPython.noop),
    ]
