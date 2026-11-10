from django.db import migrations

GROUPS = ["GEIDA reviewers", "GEIDA analysts"]


def create(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in GROUPS:
        Group.objects.get_or_create(name=name)


def remove(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=GROUPS).delete()


class Migration(migrations.Migration):
    """Role groups: reviewers (publish projects) and analysts (Analytics workspace). Assign people in /admin."""

    dependencies = [("projects", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create, remove)]
