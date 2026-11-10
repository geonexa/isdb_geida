# Users and roles

GEIDA uses Django accounts and groups. Groups are created automatically by a database
migration (`projects/0002_user_groups`); administrators assign people to them in
`/admin` → *Users*.

| Role | How a person gets it | Can |
|---|---|---|
| **Visitor** | Not signed in | Browse the public site, published projects and the Data Catalog |
| **User** | Registers and verifies their email | Create projects, edit their own drafts, run analyses on their projects, export maps |
| **Analyst** | Member of the group `GEIDA analysts` | Everything a user can, plus the Analytics GIS workspace when it is restricted (see below) |
| **Reviewer** | Member of the group `GEIDA reviewers`, or Django staff | See and edit all projects, publish or return submissions, accept or reject evidence |
| **Administrator** | Django superuser | Everything, plus `/admin`: users, groups, reference tables |

## Project visibility

| Project status | Owner | Reviewers | Other users | Visitors |
|---|---|---|---|---|
| Draft | read, edit | read, edit | — | — |
| Under review | read | read, edit, publish, return | — | — |
| Published | read | read, edit | read | read |

## Creating the first administrator

```bash
cd backend
conda activate geida
python manage.py createsuperuser
```

Then sign in at `/admin` and add other people to the reviewer or analyst groups.

## Restricting the Analytics workspace

Today the Analytics workspace is open to everyone. To limit it to analysts (staff,
reviewers and the `GEIDA analysts` group), add `"roles": ["analyst"]` to the
`analytics` section in `backend/apps/core/modules.py`. The page then shows a
"locked" message to other users.

!!! note "Single sign-on"
    Accounts are local to GEIDA today. Integration with IsDB's identity provider
    (Microsoft Entra ID) is an open decision for the hand-over.
