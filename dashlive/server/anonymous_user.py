from flask_login import AnonymousUserMixin

class AnonymousUser(AnonymousUserMixin):
    def has_permission(self, *args) -> bool:
        return False
