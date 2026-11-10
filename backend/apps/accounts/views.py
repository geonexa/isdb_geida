"""
Accounts API (JSON, session cookie + CSRF).

    GET  /api/auth/csrf/                          sets the csrftoken cookie
    GET  /api/auth/me/                            {"user": {...} | null}
    POST /api/auth/sign-in/                       {username, password, remember}
    POST /api/auth/sign-out/
    POST /api/auth/register/                      {first_name, last_name, email, password1, password2, accept}
    GET  /api/auth/verify/                        pending verification (masked email, resend wait)
    POST /api/auth/verify/                        {code}
    POST /api/auth/verify/resend/
    POST /api/auth/password-reset/                {email}
    GET  /api/auth/password-reset/<uid>/<token>/  {"valid": bool}
    POST /api/auth/password-reset/<uid>/<token>/  {new_password1, new_password2}
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.api import BadRequest, error, form_errors, json_body

from . import otp
from .forms import NewPasswordForm, RegisterForm, ResetRequestForm, SignInForm, VerifyForm

log = logging.getLogger(__name__)
User = get_user_model()
BACKEND = "apps.accounts.backends.EmailOrUsernameBackend"


from apps.projects.access import is_analyst, is_reviewer  # noqa: E402


def _user(u):
    if not u or not u.is_authenticated:
        return None
    return {
        "id": u.pk,
        "email": u.email,
        "username": u.get_username(),
        "first_name": u.first_name,
        "last_name": u.last_name,
        "full_name": u.get_full_name() or u.get_username(),
        "is_staff": u.is_staff,
        "is_reviewer": is_reviewer(u),
        "is_analyst": is_analyst(u),
    }


def _mask(email):
    name, _, domain = email.partition("@")
    shown = name[:2] if len(name) > 2 else name[:1]
    return f"{shown}{'•' * max(1, len(name) - len(shown))}@{domain}"


def _verify_state(request):
    data = otp.pending(request)
    if not data:
        return None
    return {
        "masked_email": _mask(data["email"]),
        "resend_wait": otp.seconds_until_resend(request),
        "minutes": otp.OTP_TTL // 60,
        # Shown on the page in development only, to test without email.
        "dev_code": data.get("dev_code") if settings.DEBUG else None,
    }


def _frontend_url(request):
    return settings.FRONTEND_URL or request.build_absolute_uri("/").rstrip("/")



@ensure_csrf_cookie
@require_GET
def csrf(request):
    return JsonResponse({"csrfToken": get_token(request)})


@ensure_csrf_cookie
@require_GET
def me(request):
    return JsonResponse({"user": _user(request.user)})


@require_POST
def sign_in(request):
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    ident = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    form = SignInForm(request, data={"username": ident, "password": password})
    if form.is_valid():
        user = form.get_user()
        login(request, user, backend=BACKEND)
        if not data.get("remember", True):
            request.session.set_expiry(0)  # end when the browser closes
        return JsonResponse({"user": _user(user)})

    # Right password but unverified account: send a fresh code and go verify.
    if ident and password:
        user = User.objects.filter(Q(username__iexact=ident) | Q(email__iexact=ident)).first()
        if user and not user.is_active and user.check_password(password) and user.email:
            try:
                otp.start(request, user)
            except Exception:  # noqa: BLE001
                log.exception("Couldn't send the verification email")
                return error("We couldn't send the verification email. Try again in a few minutes.", 503)
            return JsonResponse({"verify": _verify_state(request)}, status=403)
    if not ident or not password:
        return error("Enter your email (or username) and password.")
    return error(SignInForm.error_messages["invalid_login"])


@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({"user": None})


@require_POST
def register(request):
    if request.user.is_authenticated:
        return error("You're already signed in.")
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    form = RegisterForm(data={k: data.get(k, "") for k in ("first_name", "last_name", "email", "password1", "password2")}
                        | {"accept": "on" if data.get("accept") else ""})
    if not form.is_valid():
        return form_errors(form)
    user = form.save()
    email_failed = False
    try:
        otp.start(request, user)
    except Exception:  # noqa: BLE001
        log.exception("Couldn't send the verification email")
        email_failed = True
    return JsonResponse({"verify": _verify_state(request), "email_failed": email_failed}, status=201)


@require_http_methods(["GET", "POST"])
def verify(request):
    data = otp.pending(request)
    if not data:
        return error("Your verification session has ended. Sign in again to get a new code.", 404)
    if request.method == "GET":
        return JsonResponse({"verify": _verify_state(request)})

    try:
        body = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    form = VerifyForm({"code": str(body.get("code", "")).strip()})
    if not form.is_valid():
        return form_errors(form)
    ok, message = otp.check(request, form.cleaned_data["code"])
    if not ok:
        return error(message, verify=_verify_state(request))
    user = User.objects.get(pk=data["user_id"])
    user.is_active = True
    user.save(update_fields=["is_active"])
    otp.clear(request)
    login(request, user, backend=BACKEND)
    return JsonResponse({"user": _user(user)})


@require_POST
def verify_resend(request):
    data = otp.pending(request)
    if not data:
        return error("Your verification session has ended. Sign in again to get a new code.", 404)
    wait = otp.seconds_until_resend(request)
    if wait:
        return error(f"Wait {wait} seconds before asking for another code.", 429, verify=_verify_state(request))
    user = User.objects.filter(pk=data["user_id"]).first()
    if not user:
        otp.clear(request)
        return error("This account no longer exists. Register again.", 404)
    try:
        otp.start(request, user)
    except Exception:  # noqa: BLE001
        log.exception("Couldn't send the verification email")
        return error("We couldn't send the email. Try again in a few minutes.", 503)
    return JsonResponse({"verify": _verify_state(request)})


@require_POST
def password_reset(request):
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    form = ResetRequestForm(data={"email": data.get("email", "")})
    if not form.is_valid():
        return form_errors(form)
    try:
        form.save(
            request=request,
            use_https=request.is_secure(),
            subject_template_name="accounts/email/password_reset_subject.txt",
            email_template_name="accounts/email/password_reset.txt",
            extra_email_context={"reset_base": f"{_frontend_url(request)}/accounts/password-reset"},
        )
    except Exception:  # noqa: BLE001
        log.exception("Couldn't send the password reset email")
        return error("We couldn't send the email. Try again in a few minutes.", 503)
    # Same answer whether or not the account exists.
    return JsonResponse({"sent": True})


def _reset_user(uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    return user if default_token_generator.check_token(user, token) else None


@require_http_methods(["GET", "POST"])
def password_reset_confirm(request, uidb64, token):
    user = _reset_user(uidb64, token)
    if request.method == "GET":
        return JsonResponse({"valid": user is not None})
    if user is None:
        return error("This link no longer works. Ask for a new one.", 400, valid=False)
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    form = NewPasswordForm(user, data={"new_password1": data.get("new_password1", ""), "new_password2": data.get("new_password2", "")})
    if not form.is_valid():
        return form_errors(form)
    form.save()
    return JsonResponse({"done": True})
