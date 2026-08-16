from passlib.context import CryptContext
import hashlib
import hmac

from app.core.config import SECRET_KEY

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
):
    return pwd_context.verify(
        plain_password,
        hashed_password
    )


def recovery_pin_digest(pin: str) -> str:
    """Create a deterministic keyed digest; never store the recovery PIN."""
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"recovery-pin:{pin}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
