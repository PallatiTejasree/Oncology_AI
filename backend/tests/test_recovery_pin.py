import unittest

from app.core.security import recovery_pin_digest
from app.schemas.user import ChangeRecoveryPin, ForgotEmail, UserRegister


class RecoveryPinTests(unittest.TestCase):
    def test_digest_is_stable_and_does_not_contain_pin(self):
        first = recovery_pin_digest("482913")
        self.assertEqual(first, recovery_pin_digest("482913"))
        self.assertNotIn("482913", first)
        self.assertEqual(len(first), 64)

    def test_registration_accepts_four_or_six_digits(self):
        UserRegister(email="person@example.com", password="password123", recovery_pin="4829")
        ForgotEmail(recovery_pin="482913")

    def test_rejects_other_pin_lengths(self):
        with self.assertRaises(ValueError):
            ForgotEmail(recovery_pin="12345")

    def test_change_pin_requires_four_or_six_digits(self):
        value = ChangeRecoveryPin(current_password="password123", new_recovery_pin="928374")
        self.assertEqual(value.new_recovery_pin, "928374")


if __name__ == "__main__":
    unittest.main()
