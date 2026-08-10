import unittest
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth.jwt_handler import create_access_token, decode_access_token
from app.core.config import ALGORITHM, SECRET_KEY


class JwtTests(unittest.TestCase):
    def test_created_token_contains_subject_and_email(self):
        token = create_access_token({"sub": "42", "email": "doctor@example.com"})
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["email"], "doctor@example.com")
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)

    def test_invalid_token_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_access_token("not-a-jwt")

    def test_expired_token_is_rejected(self):
        token = jwt.encode(
            {"sub": "42", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with self.assertRaises(ValueError):
            decode_access_token(token)


if __name__ == "__main__":
    unittest.main()
