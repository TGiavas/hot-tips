"""Run one community-spreadsheet sync cycle.

Thin wrapper around :func:`arena.sync.sync_spreadsheet_once` suitable for
cron / Fly scheduled-machines / ad-hoc operator use:

    docker compose run --rm backend uv run python manage.py sync_spreadsheet

Exit codes:

* 0 -- the sync ran (status ``ok`` or ``skipped``)
* 1 -- the sync errored (status ``error``); the message is printed to stderr

Status / counts are always written to the singleton
:class:`arena.models.SpreadsheetSyncConfig` row regardless of exit code so the
admin and the API can surface diagnostics either way.
"""
from __future__ import annotations

import sys

from django.core.management.base import BaseCommand

from arena.models import SpreadsheetSyncConfig
from arena.sync import sync_spreadsheet_once


class Command(BaseCommand):
    help = "Fetch the community spreadsheet and additively apply its tips."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Bypass the ``enabled`` master switch (still respects the "
                "date gate; a stale sheet still skips)."
            ),
        )

    def handle(self, *args, force: bool = False, **options) -> None:
        result = sync_spreadsheet_once(force=force)
        if result.status == SpreadsheetSyncConfig.Status.OK:
            self.stdout.write(self.style.SUCCESS(f"ok: {result.message}"))
        elif result.status == SpreadsheetSyncConfig.Status.SKIPPED:
            self.stdout.write(self.style.WARNING(f"skipped: {result.message}"))
        else:
            self.stderr.write(self.style.ERROR(f"error: {result.message}"))
            sys.exit(1)
