from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta
from bson import ObjectId
import httpx
import logging

from app.schemas.schemas import (
    UserSignup, UserLogin, GoogleLoginRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    TokenResponse, RefreshTokenRequest, ChangePasswordRequest
)
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, generate_secure_token
)
from app.core.database import get_db
from app.core.config import settings
from app.utils.email import send_verification_email, send_password_reset_email, send_welcome_email
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


def serialize_user(user: dict) -> dict:
    user["id"] = str(user["_id"])
    user.pop("_id", None)
    user.pop("password_hash", None)
    user.pop("verification_token", None)
    user.pop("reset_token", None)
    user.pop("reset_token_expires", None)
    return user


# ─── Signup ───────────────────────────────────────────────────────────────────

@router.post("/signup", status_code=201)
async def signup(data: UserSignup, background_tasks: BackgroundTasks):
    db = get_db()

    # Check duplicates
    if await db.users.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Email already registered.")
    if await db.users.find_one({"username": data.username}):
        raise HTTPException(status_code=400, detail="Username already taken.")

    verification_token = generate_secure_token()
    user_doc = {
        "email": data.email,
        "username": data.username,
        "full_name": data.full_name or "",
        "password_hash": hash_password(data.password),
        "avatar_url": None,
        "bio": "",
        "role": "user",
        "is_verified": False,
        "is_banned": False,
        "auth_provider": "email",
        "google_id": None,
        "verification_token": verification_token,
        "verification_token_expires": datetime.utcnow() + timedelta(hours=24),
        "reset_token": None,
        "reset_token_expires": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.users.insert_one(user_doc)

    background_tasks.add_task(
        send_verification_email,
        to_email=data.email,
        username=data.username,
        token=verification_token
    )

    return {
        "message": "Account created! Please check your email to verify your account.",
        "user_id": str(result.inserted_id)
    }


# ─── Verify Email ─────────────────────────────────────────────────────────────

@router.get("/verify-email")
async def verify_email(token: str, background_tasks: BackgroundTasks):
    FRONTEND = settings.FRONTEND_URL  # e.g. https://natours.ct.ws
    db = get_db()
    user = await db.users.find_one({"verification_token": token})

    if not user:
        return RedirectResponse(url=f"{FRONTEND}/verify-email.html?status=invalid", status_code=302)

    expires = user.get("verification_token_expires")
    if expires and datetime.utcnow() > expires:
        return RedirectResponse(url=f"{FRONTEND}/verify-email.html?status=expired", status_code=302)

    if user.get("is_verified"):
        return RedirectResponse(url=f"{FRONTEND}/verify-email.html?status=already", status_code=302)

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "is_verified": True,
            "verification_token": None,
            "verification_token_expires": None,
            "updated_at": datetime.utcnow()
        }}
    )
    background_tasks.add_task(
        send_welcome_email,
        to_email=user["email"],
        username=user.get("username") or user.get("full_name") or "User"
    )
    # Redirect to frontend with success status — short param, no token
    return RedirectResponse(url=f"{FRONTEND}/verify-email.html?status=success", status_code=302)


# ─── Resend Verification ──────────────────────────────────────────────────────

@router.post("/resend-verification")
async def resend_verification(email: str, background_tasks: BackgroundTasks):
    db = get_db()
    user = await db.users.find_one({"email": email})
    if not user:
        # Don't reveal if email exists
        return {"message": "If this email exists, a verification link has been sent."}
    if user.get("is_verified"):
        return {"message": "Email already verified."}

    token = generate_secure_token()
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "verification_token": token,
            "verification_token_expires": datetime.utcnow() + timedelta(hours=24),
            "updated_at": datetime.utcnow()
        }}
    )
    background_tasks.add_task(
        send_verification_email,
        to_email=user["email"],
        username=user.get("username") or user.get("full_name") or "User",
        token=token
    )
    return {"message": "If this email exists, a verification link has been sent."}


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin):
    db = get_db()
    user = await db.users.find_one({"email": data.email})
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.get("is_verified"):
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Please check your inbox."
        )
    if user.get("is_banned"):
        raise HTTPException(status_code=403, detail="Account has been banned.")

    user_id = str(user["_id"])
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})

    # Save refresh token hash
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


# ─── Google OAuth ─────────────────────────────────────────────────────────────

@router.post("/google", response_model=TokenResponse)
async def google_login(data: GoogleLoginRequest):
    db = get_db()

    # Verify Google ID token
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={data.id_token}"
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token.")

    google_data = resp.json()
    if google_data.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Google token audience mismatch.")

    google_id = google_data.get("sub")
    email = google_data.get("email")
    name = google_data.get("name", "")
    picture = google_data.get("picture", "")
    email_verified = google_data.get("email_verified") == "true"

    if not email_verified:
        raise HTTPException(status_code=400, detail="Google account email not verified.")

    # Find or create user
    user = await db.users.find_one({"$or": [{"google_id": google_id}, {"email": email}]})
    if user:
        # Link Google if not already
        updates = {"last_login": datetime.utcnow()}
        if not user.get("google_id"):
            updates["google_id"] = google_id
            updates["auth_provider"] = "google"
        if not user.get("avatar_url") and picture:
            updates["avatar_url"] = picture
        await db.users.update_one({"_id": user["_id"]}, {"$set": updates})
    else:
        # Create new user
        username_base = email.split("@")[0].lower()
        username = username_base
        suffix = 1
        while await db.users.find_one({"username": username}):
            username = f"{username_base}{suffix}"
            suffix += 1

        user_doc = {
            "email": email,
            "username": username,
            "full_name": name,
            "password_hash": None,
            "avatar_url": picture,
            "bio": "",
            "role": "user",
            "is_verified": True,
            "is_banned": False,
            "auth_provider": "google",
            "google_id": google_id,
            "verification_token": None,
            "reset_token": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_login": datetime.utcnow(),
        }
        result = await db.users.insert_one(user_doc)
        user = await db.users.find_one({"_id": result.inserted_id})

    user_id = str(user["_id"])
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


# ─── Refresh Token ────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshTokenRequest):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    user_id = payload.get("sub")
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user or user.get("is_banned"):
        raise HTTPException(status_code=401, detail="User not found or banned.")

    access_token = create_access_token({"sub": user_id})
    new_refresh = create_refresh_token({"sub": user_id})
    return {"access_token": access_token, "refresh_token": new_refresh, "token_type": "bearer"}


# ─── Forgot Password ──────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    db = get_db()
    user = await db.users.find_one({"email": data.email})
    # Always return same message to prevent email enumeration
    if user and user.get("auth_provider") == "email":
        token = generate_secure_token()
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "reset_token": token,
                "reset_token_expires": datetime.utcnow() + timedelta(hours=1),
                "updated_at": datetime.utcnow()
            }}
        )
        background_tasks.add_task(
            send_password_reset_email,
            to_email=user["email"],
            username=user.get("username") or user.get("full_name") or "User",
            token=token
        )
    return {"message": "If this email is registered, a password reset link has been sent."}


# ─── Reset Password GET (email link → validate token → redirect to frontend) ──
# Email links point here. We validate the token, then redirect to frontend
# with a short safe session key. InfinityFree blocks long tokens in URLs.

@router.get("/reset-password")
async def reset_password_redirect(token: str):
    FRONTEND = settings.FRONTEND_URL
    db = get_db()
    user = await db.users.find_one({"reset_token": token})

    if not user:
        return RedirectResponse(url=f"{FRONTEND}/reset-password.html?status=invalid", status_code=302)

    expires = user.get("reset_token_expires")
    if not expires or datetime.utcnow() > expires:
        return RedirectResponse(url=f"{FRONTEND}/reset-password.html?status=expired", status_code=302)

    # Store a short session key that maps to the real token (valid 30 min)
    session_key = generate_secure_token(16)  # short 16-char safe key
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "reset_session_key": session_key,
            "reset_session_expires": datetime.utcnow() + timedelta(minutes=30),
        }}
    )
    # Redirect with short session key — safe for InfinityFree
    return RedirectResponse(url=f"{FRONTEND}/reset-password.html?key={session_key}", status_code=302)


# ─── Reset Password POST (submit new password with session key) ───────────────

@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest):
    db = get_db()

    # Support both old token field and new session_key field
    user = await db.users.find_one({
        "$or": [
            {"reset_token": data.token},
            {"reset_session_key": data.token}
        ]
    })
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Please request a new one.")

    # Check expiry — support both expiry fields
    now = datetime.utcnow()
    token_exp = user.get("reset_token_expires")
    session_exp = user.get("reset_session_expires")
    expires = session_exp or token_exp
    if not expires or now > expires:
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": hash_password(data.new_password),
            "reset_token": None,
            "reset_token_expires": None,
            "reset_session_key": None,
            "reset_session_expires": None,
            "updated_at": datetime.utcnow()
        }}
    )
    return {"message": "Password reset successfully. You can now log in."}


# ─── Change Password ──────────────────────────────────────────────────────────

@router.post("/change-password")
async def change_password(data: ChangePasswordRequest, current_user=Depends(get_current_user)):
    if not current_user.get("password_hash"):
        raise HTTPException(status_code=400, detail="Cannot change password for Google accounts.")
    if not verify_password(data.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    db = get_db()
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {
            "password_hash": hash_password(data.new_password),
            "updated_at": datetime.utcnow()
        }}
    )
    return {"message": "Password changed successfully."}


# ─── Get Current User ─────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    return serialize_user(dict(current_user))
