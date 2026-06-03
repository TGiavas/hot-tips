"""Schema + data migration for the community-spreadsheet sync feature.

Three things happen here:

1. ``DailyTipSelection.external_submitter_name`` and
   ``DailyTipAuditLog.external_actor_name`` are added so the UI can render
   spreadsheet-imported tips as ``"<name> (Spreadsheet)"`` without minting
   a real Django ``User`` for every contributor named in the sheet.

2. The :class:`arena.models.SpreadsheetSyncConfig` singleton table is
   created, and ``pk=1`` is seeded with default values via the data
   migration so :meth:`SpreadsheetSyncConfig.get_solo` never has to race on
   first access.

3. The ``spreadsheet-sync`` system user is created (``is_active=False``,
   ``is_staff=False``, unusable password). It owns every sync-imported
   ``DailyTipSelection`` row as the ``submitted_by`` FK, while the real
   contributor name lives in the new ``external_submitter_name`` field.
"""
from __future__ import annotations

from django.conf import settings
from django.db import migrations, models


SPREADSHEET_SYNC_USERNAME = "spreadsheet-sync"


def create_system_user_and_config(apps, schema_editor) -> None:
    User = apps.get_model(settings.AUTH_USER_MODEL.split(".", 1)[0], "User")
    # The ``User`` model the apps registry exposes is the historical one for
    # this migration — it has ``set_unusable_password`` available via the
    # default manager but no ``create_user`` shortcut, so we go through the
    # plain ``objects.create`` path and set the password to something
    # explicitly unusable. The user is also flagged inactive so it can never
    # log in even by accident.
    user, created = User.objects.get_or_create(
        username=SPREADSHEET_SYNC_USERNAME,
        defaults={
            "is_active": False,
            "is_staff": False,
            "is_superuser": False,
            "first_name": "Spreadsheet sync",
            "email": "",
        },
    )
    if created:
        # ``set_unusable_password`` isn't on the historical model, but
        # writing a leading ``!`` produces the same effect: Django treats
        # any hash starting with ``!`` as unusable.
        user.password = "!"
        user.save(update_fields=["password"])

    SpreadsheetSyncConfig = apps.get_model("arena", "SpreadsheetSyncConfig")
    SpreadsheetSyncConfig.objects.get_or_create(
        pk=1,
        defaults={
            "share_url": "",
            "enabled": True,
            "last_status": "never_run",
            "last_message": "",
            "last_added_count": 0,
            "last_skipped_count": 0,
        },
    )


def remove_system_user_and_config(apps, schema_editor) -> None:
    # Best-effort reverse: drop the singleton config and the system user.
    # If sync-imported selections still reference the system user, the
    # PROTECT FK will block the delete — that's intentional, the operator
    # should clean up sync rows first.
    SpreadsheetSyncConfig = apps.get_model("arena", "SpreadsheetSyncConfig")
    SpreadsheetSyncConfig.objects.filter(pk=1).delete()
    User = apps.get_model(settings.AUTH_USER_MODEL.split(".", 1)[0], "User")
    User.objects.filter(username=SPREADSHEET_SYNC_USERNAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("arena", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="dailytipselection",
            name="external_submitter_name",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="dailytipauditlog",
            name="external_actor_name",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.CreateModel(
            name="SpreadsheetSyncConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "share_url",
                    models.URLField(blank=True, default="", max_length=2048),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Master switch. Disabling stops both the manual "
                            "button and the periodic auto-sync from "
                            "contacting OneDrive."
                        ),
                    ),
                ),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                (
                    "last_status",
                    models.CharField(
                        choices=[
                            ("never_run", "Never run"),
                            ("ok", "OK"),
                            ("skipped", "Skipped (sheet stale)"),
                            ("error", "Error"),
                        ],
                        default="never_run",
                        max_length=20,
                    ),
                ),
                ("last_message", models.TextField(blank=True, default="")),
                ("last_sheet_date", models.DateField(blank=True, null=True)),
                ("last_added_count", models.PositiveIntegerField(default=0)),
                (
                    "last_skipped_count",
                    models.PositiveIntegerField(default=0),
                ),
            ],
            options={
                "verbose_name": "Spreadsheet sync config",
                "verbose_name_plural": "Spreadsheet sync config",
            },
        ),
        migrations.RunPython(
            create_system_user_and_config,
            reverse_code=remove_system_user_and_config,
        ),
    ]
