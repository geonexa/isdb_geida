"""Scaffold a new analysis folder from analyses/_template/.

    python manage.py new_analysis terrain slope
    python manage.py new_analysis water catchment --title "Catchment delineation"

If the id is in analyses/planned.yaml, its title, question and phases are filled in.
"""
import re
import shutil

import yaml
from django.core.management.base import BaseCommand, CommandError

from apps.analysis.core.manifest import ID_RE
from apps.analysis.core.registry import analyses_dir, analysis_folders, read_categories


class Command(BaseCommand):
    help = "Create analyses/<category>/<id>/ (manifest, run.py, METHOD.md, tests) from the template."

    def add_arguments(self, parser):
        parser.add_argument("category", help="category id from analyses/categories.yaml")
        parser.add_argument("id", help="analysis id: lowercase letters, digits and _ (unique)")
        parser.add_argument("--title", help="title (default: from planned.yaml, or the id)")
        parser.add_argument("--question", help="the question it answers")
        parser.add_argument("--phases", help="comma-separated: preparation,implementation,completion")

    def handle(self, *args, category, id, title=None, question=None, phases=None, **opts):
        root = analyses_dir()
        cats = {c["id"] for c in read_categories()}
        if category not in cats:
            raise CommandError(f"Unknown category '{category}'. Choose one of: {', '.join(sorted(cats))}.")
        if not re.match(ID_RE, id):
            raise CommandError("The id must start with a letter and use lowercase letters, digits and _ (2–59 characters).")
        if id in analysis_folders():
            raise CommandError(f"An analysis '{id}' already exists: {analysis_folders()[id]}")
        dest = root / category / id
        if dest.exists():
            raise CommandError(f"{dest} already exists.")

        planned = {}
        path = root / "planned.yaml"
        if path.exists():
            for p in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("planned", []) or []:
                if p["id"] == id:
                    planned = p
                    if p["category"] != category:
                        self.stderr.write(self.style.WARNING(
                            f"planned.yaml lists '{id}' under '{p['category']}', not '{category}'."))
        title = title or planned.get("title") or id.replace("_", " ").capitalize()
        question = question or planned.get("question") or "What does this analysis answer?"
        phase_list = phases.split(",") if phases else planned.get("phases") or ["preparation"]
        values = {
            "{{id}}": id, "{{category}}": category, "{{title}}": title, "{{question}}": question,
            "{{phases}}": "[" + ", ".join(phase_list) + "]",
            "{{class}}": "".join(w.capitalize() for w in id.split("_")),
        }

        template = root / "_template"
        if not template.exists():
            raise CommandError(f"The template folder is missing: {template}")
        cat_dir = root / category
        cat_dir.mkdir(exist_ok=True)
        (cat_dir / "__init__.py").touch()  # so the test runner finds the analysis' tests
        shutil.copytree(template, dest, ignore=shutil.ignore_patterns("__pycache__"))
        for f in sorted(dest.rglob("*")):
            if f.is_file() and f.suffix in (".py", ".yaml", ".md"):
                text = f.read_text(encoding="utf-8")
                for k, v in values.items():
                    text = text.replace(k, v)
                f.write_text(text, encoding="utf-8")
            if "{{id}}" in f.name:
                f.rename(f.with_name(f.name.replace("{{id}}", id)))

        rel = dest.relative_to(root.parent)
        self.stdout.write(self.style.SUCCESS(f"Created {rel}/"))
        self.stdout.write("Next: edit manifest.yaml and run.py, fill in METHOD.md, then\n"
                          f"  python manage.py check_analyses\n"
                          f"  python manage.py test analyses.{category}.{id}\n"
                          f"  python manage.py run_analysis {id} --project <CODE>")
