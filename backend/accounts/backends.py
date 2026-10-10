from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None or password is None:
            return None
        identifier = username.strip()
        users = list(User.objects.filter(Q(username=identifier) | Q(email__iexact=identifier))[:2])
        if len(users) != 1:
            # Mantém o custo de hash inclusive para conta inexistente ou ambígua.
            User().set_password(password)
            return None
        user = users[0]
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
