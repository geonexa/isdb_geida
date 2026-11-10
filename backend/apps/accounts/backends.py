from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Sign in with either an email address or a username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        user = (
            User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username))
            .order_by("id")
            .first()
        )
        if user is None:
            User().set_password(password)  # equalise timing with a real check
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
