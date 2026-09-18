from datetime import datetime, timezone
from typing import Optional

from app.services.auth_service import (
    generate_otp,
    get_otp_expiry,
)


# Temporary in-memory user + OTP storage.
# We will replace this with PostgreSQL later.
users = {}


def normalize_identifier(identifier: str) -> str:
    return identifier.strip().lower()


def create_or_get_user(identifier: str) -> dict:
    identifier = normalize_identifier(identifier)

    if identifier not in users:
        users[identifier] = {
            "id": str(len(users) + 1),
            "identifier": identifier,
            "created_at": datetime.now(timezone.utc),
            "otp": None,
            "otp_created_at": None,
            "otp_expires_at": None,
        }

    return users[identifier]


def create_user_otp(identifier: str) -> dict:
    user = create_or_get_user(identifier)

    otp = generate_otp()
    now = datetime.now(timezone.utc)
    expires_at = get_otp_expiry()

    user["otp"] = otp
    user["otp_created_at"] = now
    user["otp_expires_at"] = expires_at

    return {
        "user": user,
        "otp": otp,
        "expires_at": expires_at,
    }


def get_user(identifier: str) -> Optional[dict]:
    identifier = normalize_identifier(identifier)
    return users.get(identifier)


def clear_user_otp(identifier: str) -> None:
    user = get_user(identifier)

    if user:
        user["otp"] = None
        user["otp_created_at"] = None
        user["otp_expires_at"] = None