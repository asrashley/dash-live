#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import unittest

from passlib.context import CryptContext

from dashlive.server.models.user import User

class TestUserModel(unittest.TestCase):
    def test_password_hashing(self) -> None:
        user: User = User(username="testuser")
        user.set_password("securepassword")
        self.assertTrue(user.check_password("securepassword"))
        self.assertFalse(user.check_password("wrongpassword"))

    def test_password_upgrade(self) -> None:
        cleartext: str = r'suuuperSecret!'
        user: User = User(username="testuser")
        password_context: CryptContext = CryptContext(
            schemes=["pbkdf2_sha256"],
        )
        user.password = password_context.hash(cleartext)
        self.assertTrue(user.check_password(cleartext))
        self.assertNotEqual(user.password, password_context.hash(cleartext))

        password_context = CryptContext(
            schemes=["bcrypt", "pbkdf2_sha256"],
            deprecated="auto",
        )
        user.password = password_context.hash(cleartext)
        self.assertTrue(user.check_password(cleartext))
        self.assertNotEqual(user.password, password_context.hash(cleartext))

    def test_existing_password(self) -> None:
        user: User = User(username="admin")
        user.password = r"$2b$12$/aZuWm9kstaiW3U3zSF03.VDMpBrDEL.ADFdNaAlJO53THAO/T.sa"
        self.assertTrue(user.check_password("admin"))


if __name__ == '__main__':
    unittest.main()
