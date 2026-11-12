# Maintaining the documentation

This site is built with [MkDocs](https://www.mkdocs.org) and the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. Its source is the
Markdown in `docs/`, its configuration `mkdocs.yml` at the repository root.

**The documentation is part of every change.** A pull request or release that changes
behaviour, configuration, setup or deployment also updates the pages concerned, the
[Changelog](../changelog.md) and, when administrators must act, an
[Update note](../updates/index.md).

## Preview locally

The docs tools install into the same `geida` conda environment as the backend. They are
pure-Python packages, so they don't touch the conda-forge geospatial libraries.

```bash
conda activate geida
pip install -r docs/requirements.txt        # once, and after docs/requirements.txt changes

mkdocs serve                                # from the repository root
                                            # http://127.0.0.1:8001, reloads on save
```

The built `site/` folder is git-ignored. GEIDA itself doesn't depend on these packages,
so servers that only run the platform don't need them.

## Build

```bash
mkdocs build                                # -> site/
```

`strict: true` in `mkdocs.yml` makes the build fail on broken links or pages missing from
the navigation. Fix warnings; don't switch strict mode off.

## Publish

The site is published to **GitHub Pages** at <https://geonexa.github.io/isdb_geida/> by the
workflow `.github/workflows/docs.yml`. It runs on every push to `main` that changes `docs/`,
`mkdocs.yml` or the workflow, and can be run by hand from the repository's **Actions** tab
(*Docs* → *Run workflow*). It installs `docs/requirements.txt`, runs `mkdocs build --strict`
(a broken link fails the run and nothing is published) and deploys `site/`.

One-time setup, by a repository admin: **Settings → Pages → Build and deployment → Source:
GitHub Actions**.

Pages excluded in `mkdocs.yml` (`exclude_docs`: plan, decisions, planning notes) are not on the
site, but they are still in the repository, so anyone who can see the repository can read them.

The built `site/` folder is plain static HTML, so it can also be served elsewhere:

| Option | How |
|---|---|
| Same server as GEIDA | Copy `site/` to e.g. `/var/www/geida-docs` and add an Apache `Alias /docs/ /var/www/geida-docs/` |
| Internal file share | Zip `site/` and open `index.html` (search works offline) |

## Structure

```
docs/
├── index.md                    Home
├── introduction/               what GEIDA is, project cycle, features, roles, glossary
├── architecture/               components, backend, frontend, data sources, modules, security
├── setup/                      prerequisites, local development, configuration, reference data, troubleshooting
├── deploy/                     overview, first-time installation, releases, operations
├── development/                workflow, adding a module, testing, this page
├── changelog.md                every change, by release date
├── updates/                    release notes with upgrade steps, one page per update
├── plan.md, decisions.md       roadmap and decision log (in the repository, not published)
├── specs/                      feature specifications (Reference; some kept unpublished)
├── open-map-services.md        external map services (Reference)
└── assets/                     logos and the stylesheet
```

## Writing style

- Write for someone who has never seen GEIDA: say what a thing is before how to use it.
- One topic per page; link instead of repeating.
- Commands in fenced code blocks, ready to copy, with the directory they run in.
- Exact names: file paths, settings, endpoints and commands as they are in the code.
- Tables for reference information; numbered steps for procedures.
- Admonitions sparingly: `!!! note`, `!!! tip`, `!!! warning`, `!!! danger`.
- Diagrams in Mermaid (` ```mermaid `) so they stay editable.
- British English, as in the rest of the platform.

## Adding a page

1. Create the Markdown file in the right section folder.
2. Add it to `nav:` in `mkdocs.yml`.
3. Run `mkdocs build` and fix any warnings.

## Generated pages

The **Analyses** section (`docs/analyses/`) is written from the analyses themselves (each `manifest.yaml` and
`METHOD.md`), so don't edit those pages by hand. After adding or changing an analysis:

```bash
cd backend
python manage.py document_analyses            # rewrite docs/analyses/
python manage.py document_analyses --check    # what the test suite checks: fails if the pages are out of date
```

A new category page also needs a line under `Analyses:` in `mkdocs.yml`.

## Recording a change

For every release:

1. **Changelog**: add the changes under a new `## YYYY-MM-DD` heading at the top of
   [changelog.md](../changelog.md), grouped as *Added*, *Changed*, *Fixed*, *Removed*,
   *Security*. One line per change, written for a reader who wasn't there.
2. **Update note** (when there is anything to do by hand, or a change users will notice):
   copy the template in [Updates](../updates/index.md) to `updates/YYYY-MM-DD.md`, fill it
   in, and add it to `nav:` (newest first) and to the list on the Updates page.
3. **Pages**: update every page whose content changed (setup steps, settings, endpoints,
   screenshots).
