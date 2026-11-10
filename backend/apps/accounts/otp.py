"""
Email verification codes, kept in the session (no database table needed).
A code is 6 digits, stored hashed, valid for OTP_TTL seconds, with a limited
number of attempts and a cooldown between resends.
"""
import hashlib
import hmac
import secrets
import time

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

SESSION_KEY = "geida_verify"
OTP_TTL = getattr(settings, "OTP_TTL_SECONDS", 600)
OTP_MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_COOLDOWN = getattr(settings, "OTP_RESEND_COOLDOWN", 60)


def _hash(code):
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def pending(request):
    return request.session.get(SESSION_KEY)


def start(request, user):
    """Create a code for this user, email it, and remember it in the session."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    data = {
        "user_id": user.pk,
        "email": user.email,
        "hash": _hash(code),
        "expires": time.time() + OTP_TTL,
        "attempts": 0,
        "sent_at": time.time(),
    }
    if settings.DEBUG:
        data["dev_code"] = code  # shown on screen in development only
    request.session[SESSION_KEY] = data

    context = {"user": user, "code": code, "minutes": OTP_TTL // 60}
    send_mail(
        subject="Your GEIDA verification code",
        message=render_to_string("accounts/email/verification_code.txt", context),
        from_email=None,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return data


def seconds_until_resend(request):
    data = pending(request)
    if not data:
        return 0
    return max(0, int(OTP_RESEND_COOLDOWN - (time.time() - data["sent_at"])))


def check(request, code):
    """Return (ok, error_message)."""
    data = pending(request)
    if not data:
        return False, "Your verification session has ended. Sign in again to get a new code."
    if time.time() > data["expires"]:
        return False, "This code has expired. Send a new code and try again."
    if data["attempts"] >= OTP_MAX_ATTEMPTS:
        return False, "Too many incorrect attempts. Send a new code and try again."
    data["attempts"] += 1
    request.session[SESSION_KEY] = data
    if not hmac.compare_digest(_hash(code), data["hash"]):
        left = OTP_MAX_ATTEMPTS - data["attempts"]
        return False, f"That code isn't right. {left} attempt{'s' if left != 1 else ''} left."
    return True, ""


def clear(request):
    request.session.pop(SESSION_KEY, None)
