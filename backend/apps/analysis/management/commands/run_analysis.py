"""Run one analysis for a project on this machine, without the queue (for developing and checking).

    python manage.py run_analysis buildings --project ABDCSD
    python manage.py run_analysis buildings --project ABDCSD --phase completion --param cell_m=250

The run is recorded like any other (it appears in the project's Analyses tab) and its
outputs are written to MEDIA_ROOT/runs/<id>/.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.analysis.core.registry import availability, sync_modules
from apps.analysis.core.runner import execute
from apps.analysis.models import PHASES, Module, ModuleRun


def _value(v):
    try:
        return json.loads(v)  # numbers, true/false, lists
    except ValueError:
        return v


class Command(BaseCommand):
    help = "Run an analysis synchronously for a project and print its results."

    def add_arguments(self, parser):
        parser.add_argument("analysis", help="analysis id")
        parser.add_argument("--project", required=True, help="project code")
        parser.add_argument("--phase", default="preparation", choices=[p for p, _ in PHASES])
        parser.add_argument("--param", action="append", default=[], metavar="NAME=VALUE", help="parameter (repeatable)")
        parser.add_argument("--force", action="store_true", help="run even if the analysis isn't ready for this project")

    def handle(self, *args, analysis, project, phase, param, force=False, **opts):
        from apps.projects.models import Project

        problems = []
        manifests = sync_modules(problems)
        for p in problems:
            self.stderr.write(self.style.WARNING(f"left out: {p}"))
        if analysis not in manifests:
            raise CommandError(f"No analysis '{analysis}'. Available: {', '.join(sorted(manifests))}.")
        m = manifests[analysis]
        try:
            proj = Project.objects.select_related("area").get(code=project)
        except Project.DoesNotExist:
            raise CommandError(f"No project '{project}'.")
        if phase not in m["phases"]:
            raise CommandError(f"'{analysis}' isn't offered in {phase} (phases: {', '.join(m['phases'])}).")
        av = availability(m, proj)
        if av["status"] != "ready" and not force:
            raise CommandError(f"Not ready for {project}: {' '.join(av['reasons'])} (use --force to try anyway)")

        params = {}
        known = {p["name"] for p in m.get("parameters", []) or []}
        for item in param:
            name, sep, value = item.partition("=")
            if not sep or name not in known:
                raise CommandError(f"Bad --param '{item}'. Parameters: {', '.join(sorted(known)) or 'none'}.")
            params[name] = _value(value)

        module = Module.objects.get(pk=analysis)
        run = ModuleRun.objects.create(project=proj, module=module, module_version=module.version, phase=phase,
                                       params=params)
        self.stdout.write(f"Run #{run.pk}: {module.title} {module.version} · {project} · {phase}")
        execute(run)
        run.refresh_from_db()
        if run.status != "done":
            self.stdout.write(run.log[-3000:])
            raise CommandError(f"Run #{run.pk} failed: {run.error}")
        self.stdout.write(self.style.SUCCESS(f"Done: {run.summary}"))
        for o in run.outputs:
            detail = f"{o['value']} {o.get('unit', '')}".strip() if o["type"] == "metric" else \
                f"{len(o.get('rows', []))} rows" if o["type"] == "table" else o.get("file", "")
            self.stdout.write(f"  {o['type']:7} {o['name']:20} {detail}")
        self.stdout.write(f"Files: {run.workdir}")
