# Updates

Update notes explain a release in more detail than the [Changelog](../changelog.md):
what users will notice, and **what administrators must do** when they deploy it. Read
every note between your server's current release and the one you are installing, oldest
first.

| Date | Update | Action needed on servers |
|---|---|---|
| 2026-11-09 | [Documentation and branding](2026-11-09.md) | No |
| 2026-11-06 | [Raster layers from cloud-optimised GeoTIFFs](2026-11-06.md) | Yes: `.env`, dependencies |
| 2026-11-02 | [Repository restructure](2026-11-02.md) | Yes: data folder, conda environment |

## Template for a new update note

Copy this into `docs/updates/YYYY-MM-DD.md`, add it to `nav:` in `mkdocs.yml` (newest
first) and to the table above.

````markdown
# YYYY-MM-DD: <short title>

**Release:** YYYY-MM-DD · **Action needed:** yes / no

## Summary

Two or three sentences: what changed and why it matters.

## What users will notice

- …

## What administrators must do

1. … (new `.env` values, data to copy, commands to run beyond `deploy.sh`)

## Compatibility

- Database migrations: yes / no (back up first if yes)
- Breaking changes to the API or URLs: …

## Related

- Changelog entry, specs, decisions
````
