from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class AllowInactiveAuthBackend(ModelBackend):
    """
    Custom authentication backend that allows authenticating users
    with is_active=False so the login view can distinguish between:
    - Invalid credentials (returns None)
    - Valid credentials but suspended account (returns user with is_active=False)

    IMPORTANT: This backend does NOT log in inactive users.
    It only allows the authenticate() function to return the user object
    when credentials are correct, so the login view can check is_active
    and show the appropriate suspension message.
    """

    def user_can_authenticate(self, user):
        """
        Override the default ModelBackend behavior which rejects inactive users.
        Return True for all users found by username/password lookup,
        letting the login view handle is_active checks with proper messaging.
        """
        return True
