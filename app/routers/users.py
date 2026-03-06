from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from datetime import datetime
from bson import ObjectId

from app.schemas.schemas import UserUpdateRequest
from app.core.database import get_db
from app.utils.dependencies import get_current_user, get_current_verified_user, get_admin_user
from app.utils.files import save_upload_file, delete_file

router = APIRouter(prefix="/users", tags=["Users"])


def serialize_user(user: dict) -> dict:
    user = dict(user)
    user["id"] = str(user["_id"])
    user.pop("_id", None)
    user.pop("password_hash", None)
    user.pop("verification_token", None)
    user.pop("reset_token", None)
    user.pop("reset_token_expires", None)
    user.pop("verification_token_expires", None)
    return user


# ─── Get public user profile ──────────────────────────────────────────────────

@router.get("/{user_id}")
async def get_user_profile(user_id: str):
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID.")
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Public profile only
    return {
        "id": str(user["_id"]),
        "username": user.get("username"),
        "full_name": user.get("full_name"),
        "avatar_url": user.get("avatar_url"),
        "bio": user.get("bio"),
        "created_at": user.get("created_at"),
    }


# ─── Update profile ───────────────────────────────────────────────────────────

@router.put("/me/profile")
async def update_profile(data: UserUpdateRequest, current_user=Depends(get_current_user)):
    db = get_db()
    updates = {}
    if data.full_name is not None:
        updates["full_name"] = data.full_name
    if data.bio is not None:
        updates["bio"] = data.bio
    if data.username is not None:
        existing = await db.users.find_one({"username": data.username.lower()})
        if existing and str(existing["_id"]) != str(current_user["_id"]):
            raise HTTPException(status_code=400, detail="Username already taken.")
        updates["username"] = data.username.lower()

    if not updates:
        return {"message": "Nothing to update."}

    updates["updated_at"] = datetime.utcnow()
    await db.users.update_one({"_id": current_user["_id"]}, {"$set": updates})
    updated = await db.users.find_one({"_id": current_user["_id"]})
    return serialize_user(updated)


# ─── Upload Avatar ────────────────────────────────────────────────────────────

@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    db = get_db()
    # Delete old avatar
    old_avatar = current_user.get("avatar_url")
    if old_avatar and not old_avatar.startswith("http"):
        await delete_file(old_avatar)

    path = await save_upload_file(file, subfolder="avatars")
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"avatar_url": path, "updated_at": datetime.utcnow()}}
    )
    return {"avatar_url": path, "message": "Avatar updated successfully."}


# ─── Get user's reviews ───────────────────────────────────────────────────────

@router.get("/{user_id}/reviews")
async def get_user_reviews(user_id: str, page: int = 1, limit: int = 10):
    db = get_db()
    try:
        uid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID.")

    skip = (page - 1) * limit
    cursor = db.reviews.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
    reviews = []
    async for r in cursor:
        r["id"] = str(r["_id"])
        r.pop("_id", None)
        reviews.append(r)

    total = await db.reviews.count_documents({"user_id": user_id})
    return {"reviews": reviews, "total": total, "page": page, "pages": -(-total // limit)}


# ─── Admin: list all users ────────────────────────────────────────────────────

@router.get("/", dependencies=[Depends(get_admin_user)])
async def list_users(page: int = 1, limit: int = 20, search: str = None):
    db = get_db()
    query = {}
    if search:
        import re
        pattern = re.compile(search, re.IGNORECASE)
        query = {"$or": [{"email": pattern}, {"username": pattern}, {"full_name": pattern}]}

    skip = (page - 1) * limit
    cursor = db.users.find(query).sort("created_at", -1).skip(skip).limit(limit)
    users = []
    async for u in cursor:
        users.append(serialize_user(u))

    total = await db.users.count_documents(query)
    return {"users": users, "total": total, "page": page, "pages": -(-total // limit)}


# ─── Admin: ban/unban user ────────────────────────────────────────────────────

@router.patch("/{user_id}/ban", dependencies=[Depends(get_admin_user)])
async def ban_user(user_id: str, ban: bool = True):
    db = get_db()
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_banned": ban, "updated_at": datetime.utcnow()}}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID.")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"User {'banned' if ban else 'unbanned'} successfully."}
