"""Small helpers shared by the JSON API views."""
import json

from django.http import JsonResponse


class BadRequest(Exception):
    pass


def json_body(request):
    """The request's JSON object, or {} for an empty body. Raises BadRequest otherwise."""
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except ValueError as exc:
        raise BadRequest("Couldn't read the request.") from exc
    if not isinstance(data, dict):
        raise BadRequest("Couldn't read the request.")
    return data


def error(message, status=400, **extra):
    return JsonResponse({"error": message, **extra}, status=status)


def form_errors(form):
    """Django form errors as {"errors": {field: [messages]}, "error": first message}."""
    errors = {field: [str(m) for m in msgs] for field, msgs in form.errors.items()}
    first = next(iter(errors.values()), ["Check the form and try again."])[0]
    return JsonResponse({"error": first, "errors": errors}, status=400)


def not_found(request, *args, **kwargs):
    return error("Not found.", status=404)
