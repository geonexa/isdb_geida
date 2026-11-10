# Project onboarding (Cycle 1, phase 1)

Status: built · Oct 2026 · Owners: Sajid, Aman

Implements "Project onboarding" and the CRI part of "Results Framework and CRI
alignment" from *GEIDA Platform Development Working Plan* (27 Oct 2026).

## Screens

| Route | Screen |
|---|---|
| `/projects` | List + map. Tabs: All, My projects, Review queue (reviewers). Filters: country, sector, stage, status, search. |
| `/projects/new` | Wizard step 1 (creates the draft). |
| `/projects/:code/edit?step=1..5` | Wizard: Identity · Area · Themes · Results · Documents. |
| `/projects/:code` | Project page: summary, map, Results Framework, GEIDA support, documents, activity; Submit / Return / Publish / Delete. |
| `/projects/import` | Route B (GEIDA template) and Route C (submission-form export), preview then commit. |

## Rules

- Status: `draft → review → published`; reviewers can return (with a comment) or publish.
- Owners edit their drafts; reviewers (staff or group **GEIDA reviewers**) edit anything.
- Anyone sees published projects; drafts only by owner and reviewers.
- Code is unique, `AAA…` + digits (e.g. UGA1072); a duplicate offers "open it" (wizard) or *update* (import).
- Valid draft = code, title, country. Submit/publish also needs sector, stage and an area.
- Every record keeps `source` (manual / import / form) and `source_info` (e.g. form submitter).
- Every change is logged (ProjectLog) and shown under Activity.

## Area of influence (step 2)

Methods: upload (GeoJSON, KML/KMZ, GeoPackage, zipped shapefile), draw, admin units
(GADM levels 1–3, from `apps.boundaries`), point + buffer, whole country.

`POST /api/projects/area/preview/` checks without saving; the user then confirms.
Every change is reported as a note, never silent: reprojection, dropped Z values,
repaired invalid geometry, ignored point/line features, ignored whole-world
placeholder polygons (Google Earth exports), merged features, share outside the
selected country. Area is computed in an equal-area projection (EPSG:6933).

## Results Framework (step 4)

Indicator fields: level, statement, unit, CRI, tier, baseline (value, year),
target (value, year), means of verification, male/female flag, geospatial role.
Picking a CRI fills name, unit, tier (TA CRI for 17.1/17.2/17.4), role and the
male/female flag; all stay editable. Warnings: CRI unit differs (e.g. ha vs km²),
CRI notes from the library, sex-disaggregation "to confirm".

CRI library: `python manage.py load_cri` reads `backend/data/isdb_cri_2025_seed.csv`
(77 CRIs; codes are data, not code; re-running updates).

## Import

- Template: `GET /api/projects/import/template/` (.xlsx with a Lists sheet).
- Submission form: Microsoft Forms export; maps code, title, location, sector,
  stage, hub (from work location), submitter; links become documents.
- Optional boundaries zip: one file per project named by code (`AZE1028.kml`).
- Suggestions the user can tick: "Entire country" → country outline; coordinates
  in the text or a close-up Google Earth link → 5 km buffer.

## API

```
GET  /api/projects/meta/                     choices, member countries, user role
GET  /api/projects/cri/?q=                   CRI search
GET  /api/projects/?status=&country=&sector=&stage=&q=&mine=1
POST /api/projects/                          create draft
GET|PATCH|DELETE /api/projects/<code>/
POST /api/projects/area/preview/             check an area (JSON or multipart)
POST|DELETE /api/projects/<code>/area/       save / remove the area
PUT  /api/projects/<code>/indicators/        replace the Results Framework
PUT  /api/projects/<code>/documents/         replace document links
POST /api/projects/<code>/submit|return|publish/
GET  /api/projects/import/template/
POST /api/projects/import/preview/           multipart: kind, file, boundaries
POST /api/projects/import/commit/            {token, rows:[{row, apply_suggestion}]}
```

## Set-up

```
pip install -r backend/requirements.txt      # adds openpyxl
python manage.py migrate
python manage.py load_cri
python manage.py load_admin_units            # GADM, for admin-unit picking and country checks
```

Tests: `python manage.py test apps.projects`.

## Not in this phase

Module availability per project (needs the module registry), evidence records and
the indicator tracker, OTL person picker (free text for now), Route C straight from
Microsoft Forms (file export for now).

## Open points

- Regional hub list (in `apps/projects/choices.py`) to confirm with IsDB.
- Project-code format exceptions.
- Edit rights by hub (today: owner + reviewers).
