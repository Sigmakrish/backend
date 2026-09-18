import os
import re
from email.message import EmailMessage

import aiosmtplib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.auth_service import (
    create_access_token,
    is_otp_valid,
)

from app.services.user_service import (
    create_user_otp,
    get_user,
    clear_user_otp,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class SendOTPRequest(BaseModel):
    identifier: str


class VerifyOTPRequest(BaseModel):
    identifier: str
    otp: str


# =========================================================
# EMAIL / PHONE VALIDATION
# =========================================================

def is_valid_email(value: str) -> bool:
    pattern = (
        r"^[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+"
        r"\.[A-Za-z]{2,}$"
    )

    return bool(
        re.fullmatch(pattern, value)
    )


def is_valid_phone(value: str) -> bool:
    value = (
        value
        .replace(" ", "")
        .replace("-", "")
    )

    return bool(
        re.fullmatch(
            r"(?:\+91)?[6-9]\d{9}",
            value
        )
    )


def normalize_phone(value: str) -> str:
    value = (
        value
        .replace(" ", "")
        .replace("-", "")
    )

    if value.startswith("+91"):
        return value

    if len(value) == 10:
        return "+91" + value

    return value


def validate_identifier(identifier: str) -> str:

    identifier = identifier.strip()

    if is_valid_email(identifier):
        return identifier.lower()

    if is_valid_phone(identifier):
        return normalize_phone(identifier)

    raise HTTPException(
        status_code=400,
        detail=(
            "Enter a valid email address "
            "or Indian phone number."
        ),
    )


# =========================================================
# SEND EMAIL OTP
# =========================================================

async def send_email_otp(
    email: str,
    otp: str,
) -> bool:

    message = EmailMessage()

    message["From"] = os.getenv(
        "SMTP_FROM",
        os.getenv("SMTP_USERNAME", ""),
    )

    message["To"] = email

    message["Subject"] = (
        "RareBook AI - Login OTP"
    )

    message.set_content(
        f"""Hello,

Your RareBook AI login OTP is:

{otp}

This OTP is valid for 5 minutes.

If you did not request this OTP,
you can safely ignore this email.

Regards,
RareBook AI
"""
    )

    try:

        smtp_host = os.getenv(
            "SMTP_HOST",
            "smtp.gmail.com",
        )

        smtp_port = int(
            os.getenv(
                "SMTP_PORT",
                "587",
            )
        )

        smtp_username = os.getenv(
            "SMTP_USERNAME"
        )

        smtp_password = os.getenv(
            "SMTP_PASSWORD"
        )

        if not smtp_username:
            print(
                "ERROR: SMTP_USERNAME is missing."
            )
            return False

        if not smtp_password:
            print(
                "ERROR: SMTP_PASSWORD is missing."
            )
            return False

        await aiosmtplib.send(
            message,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_username,
            password=smtp_password,
            start_tls=True,
        )

        print(
            f"OTP email sent successfully to {email}"
        )

        return True

    except Exception as exc:

        print(
            f"Email OTP sending failed: {exc}"
        )

        return False


# =========================================================
# SEND SMS OTP
# =========================================================

async def send_sms_otp(
    phone: str,
    otp: str,
) -> bool:

    # SMS provider will be connected later.
    print(
        f"SMS OTP is not configured yet for {phone}"
    )

    return False


# =========================================================
# SEND OTP
# =========================================================

@router.post("/send-otp")
async def send_otp(
    data: SendOTPRequest
):

    identifier = validate_identifier(
        data.identifier
    )

    result = create_user_otp(
        identifier
    )

    otp = result["otp"]

    # EMAIL
    if is_valid_email(identifier):

        sent = await send_email_otp(
            identifier,
            otp,
        )

        delivery_method = "email"

    # PHONE
    else:

        sent = await send_sms_otp(
            identifier,
            otp,
        )

        delivery_method = "sms"

    # DELIVERY FAILED
    if not sent:

        clear_user_otp(
            identifier
        )

        if delivery_method == "email":

            raise HTTPException(
                status_code=500,
                detail=(
                    "Could not send OTP email. "
                    "Please check your SMTP configuration."
                ),
            )

        raise HTTPException(
            status_code=500,
            detail=(
                "SMS OTP is not configured yet."
            ),
        )

    # SUCCESS
    return {
        "success": True,
        "message": (
            f"OTP sent successfully via "
            f"{delivery_method}."
        ),
        "identifier": identifier,
        "delivery_method": delivery_method,
        "expires_in_minutes": 5,
    }


# =========================================================
# VERIFY OTP
# =========================================================

@router.post("/verify-otp")
async def verify_otp(
    data: VerifyOTPRequest
):

    identifier = validate_identifier(
        data.identifier
    )

    user = get_user(
        identifier
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail=(
                "User not found. "
                "Please request an OTP first."
            ),
        )

    # VERIFY OTP
    if not is_otp_valid(
        user["otp_created_at"],
        user["otp_expires_at"],
        data.otp.strip(),
        user["otp"],
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired OTP.",
        )

    # CREATE JWT
    token = create_access_token(
        user_id=user["id"],
        identifier=identifier,
    )

    # REMOVE USED OTP
    clear_user_otp(
        identifier
    )

    return {
        "success": True,
        "message": "Login successful.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "identifier": identifier,
        },
    }