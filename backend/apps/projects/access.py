"""Who may see and change a project.

- Projects are for signed-in users only: visitors who aren't signed in see none (not even published ones),
  and every project API answers them with "sign in".
- Signed-in users see published projects.
- Signed-in users create projects and edit their own drafts.
- Reviewers (staff, or members of the "GEIDA reviewers" group) see and edit
  everything, return projects to draft and publish them.
"""
REVIEWER_GROUP = "GEIDA reviewers"
ANALYST_GROUP = "GEIDA analysts"  # Analytics workspace (analysts and trainers)


def is_reviewer(user):
    if not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser or user.groups.filter(name=REVIEWER_GROUP).exists()


def is_analyst(user):
    """Analytics workspace (full GIS toolbox): staff, reviewers and members of "GEIDA analysts"."""
    if not user.is_authenticated:
        return False
    return (user.is_staff or user.is_superuser
            or user.groups.filter(name__in=[ANALYST_GROUP, REVIEWER_GROUP]).exists())


def can_view(user, project):
    if not user.is_authenticated:
        return False
    if project.status == "published":
        return True
    return project.owner_id == user.id or is_reviewer(user)


def can_edit(user, project):
    if not user.is_authenticated:
        return False
    if is_reviewer(user):
        return True
    return project.owner_id == user.id and project.status == "draft"


def visible(qs, user):
    from django.db.models import Q

    if is_reviewer(user):
        return qs
    if user.is_authenticated:
        return qs.filter(Q(status="published") | Q(owner=user))
    return qs.none()
