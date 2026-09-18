import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt


JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "change-this-secret-in-production"
)

JWT_ALGORITHM = "HS256"

OTP_EXPIRY_MINUTES = 5


def generate_otp() -> str:
    """
    Generate a secure 6-digit OTP.
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def get_otp_expiry() -> datetime:
    """
    Return the time at which the OTP expires.
    """
    return (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=OTP_EXPIRY_MINUTES
        )
    )


def is_otp_valid(
    otp_created_at: datetime,
    otp_expires_at: datetime,
    submitted_otp: str,
    stored_otp: str,
) -> bool:
    """
    Validate OTP value and expiry time.
    """

    if not submitted_otp or not stored_otp:
        return False

    if submitted_otp != stored_otp:
        return False

    now = datetime.now(timezone.utc)

    if otp_expires_at.tzinfo is None:
        otp_expires_at = (
            otp_expires_at.replace(
                tzinfo=timezone.utc
            )
        )

    if otp_created_at.tzinfo is None:
        otp_created_at = (
            otp_created_at.replace(
                tzinfo=timezone.utc
            )
        )

    if now > otp_expires_at:
        return False

    return True


def create_access_token(
    user_id: str,
    identifier: str,
) -> str:
    """
    Create a JWT access token.
    """

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "identifier": identifier,
        "iat": now,
        "exp": (
            now
            + timedelta(days=7)
        ),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> dict:
    """
    Decode and validate JWT.
    """

    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )