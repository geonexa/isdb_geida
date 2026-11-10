from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import modules


@require_GET
def site(request):
    """Static site content: sections, Knowledge Hub, project cycle, components."""
    return JsonResponse({
        "primary": modules.PRIMARY,
        "hub": modules.KNOWLEDGE_HUB,
        "cycle": modules.PROJECT_CYCLE,
        "components": modules.COMPONENTS,
    })
