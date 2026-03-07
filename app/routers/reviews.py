from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.schemas.schemas import ReviewCreate, ReviewUpdate
from app.core.database import get_db
from app.utils.dependencies import get_current_verified_user
from app.utils.files import save_upload_file, delete_file

router = APIRouter(prefix="/reviews", tags=["Reviews"])

MAX_PHOTOS = 10
COLLECTION = "na_tours_reviews"


def serialize(r: dict) -> dict:
    r = dict(r)
    r["id"] = str(r["_id"])
    r.pop("_id", None)
    return r


# ── GET all reviews (public) ──────────────────────────────────────────────────
@router.get("/")
async def list_reviews(
    page:   int           = Query(1,  ge=1),
    limit:  int           = Query(10, ge=1, le=50),
    sort:   str           = Query("created_at"),
    rating: Optional[int] = Query(None, ge=1, le=5),
):
    db    = get_db()
    query = {"is_active": True}
    if rating:
        query["rating"] = rating

    sort_map = {
        "rating_high": [("rating", -1), ("created_at", -1)],
        "rating_low":  [("rating",  1), ("created_at", -1)],
        "helpful":     [("helpful_count", -1), ("created_at", -1)],
        "created_at":  [("created_at", -1)],
    }
    sort_order = sort_map.get(sort, [("created_at", -1)])
    skip       = (page - 1) * limit
    cursor     = db[COLLECTION].find(query).sort(sort_order).skip(skip).limit(limit)
    reviews    = [serialize(r) async for r in cursor]
    total      = await db[COLLECTION].count_documents(query)

    # Rating breakdown 1-5
    raw = await db[COLLECTION].aggregate([
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}}
    ]).to_list(5)
    breakdown = {item["_id"]: item["count"] for item in raw}

    # Overall average
    avg_raw    = await db[COLLECTION].aggregate([
        {"$match": {"is_active": True}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}}
    ]).to_list(1)
    avg_rating = round(avg_raw[0]["avg"], 1) if avg_raw else 0.0
    total_all  = avg_raw[0]["count"]          if avg_raw else 0

    return {
        "reviews":          reviews,
        "total":            total,
        "page":             page,
        "pages":            max(1, -(-total // limit)),
        "rating_breakdown": breakdown,
        "avg_rating":       avg_rating,
        "total_reviews":    total_all,
    }


# ── POST create review ────────────────────────────────────────────────────────
@router.post("/", status_code=201)
async def create_review(data: ReviewCreate, current_user=Depends(get_current_verified_user)):
    db      = get_db()
    user_id = str(current_user["_id"])

    existing = await db[COLLECTION].find_one({"user_id": user_id, "is_active": True})
    if existing:
        raise HTTPException(status_code=409, detail="You have already submitted a review. You can edit your existing review.")

    doc = {
        "user_id":       user_id,
        "user_name":     current_user.get("full_name") or current_user.get("username") or "Anonymous",
        "user_avatar":   current_user.get("avatar_url"),
        "rating":        data.rating,
        "title":         data.title,
        "body":          data.body,
        "trip_date":     data.trip_date,
        "trip_type":     data.trip_type,
        "photos":        [],
        "helpful_count": 0,
        "helpful_users": [],
        "is_active":     True,
        "created_at":    datetime.utcnow(),
        "updated_at":    datetime.utcnow(),
    }
    result    = await db[COLLECTION].insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


# ── POST upload up to 10 photos ───────────────────────────────────────────────
@router.post("/{review_id}/photos")
async def upload_photos(
    review_id: str,
    files: List[UploadFile] = File(...),
    current_user=Depends(get_current_verified_user),
):
    db      = get_db()
    user_id = str(current_user["_id"])
    try:
        review = await db[COLLECTION].find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your review.")

    current_count = len(review.get("photos", []))
    if current_count + len(files) > MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PHOTOS} photos allowed. You have {current_count}, trying to add {len(files)}.")

    uploaded = []
    for file in files:
        path = await save_upload_file(file, subfolder="reviews")
        uploaded.append(path)

    await db[COLLECTION].update_one(
        {"_id": review["_id"]},
        {"$push": {"photos": {"$each": uploaded}}, "$set": {"updated_at": datetime.utcnow()}}
    )
    return {"uploaded": uploaded, "total_photos": current_count + len(uploaded), "message": f"{len(uploaded)} photo(s) uploaded."}


# ── PUT edit own review ───────────────────────────────────────────────────────
@router.put("/{review_id}")
async def update_review(review_id: str, data: ReviewUpdate, current_user=Depends(get_current_verified_user)):
    db      = get_db()
    user_id = str(current_user["_id"])
    try:
        review = await db[COLLECTION].find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your review.")

    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        return {"message": "Nothing to update."}
    updates["updated_at"] = datetime.utcnow()
    await db[COLLECTION].update_one({"_id": review["_id"]}, {"$set": updates})
    updated = await db[COLLECTION].find_one({"_id": review["_id"]})
    return serialize(updated)


# ── DELETE own review ─────────────────────────────────────────────────────────
@router.delete("/{review_id}")
async def delete_review(review_id: str, current_user=Depends(get_current_verified_user)):
    db       = get_db()
    user_id  = str(current_user["_id"])
    is_admin = current_user.get("role") == "admin"
    try:
        review = await db[COLLECTION].find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review["user_id"] != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized.")
    await db[COLLECTION].update_one({"_id": review["_id"]}, {"$set": {"is_active": False, "updated_at": datetime.utcnow()}})
    return {"message": "Review deleted."}


# ── DELETE one photo ──────────────────────────────────────────────────────────
@router.delete("/{review_id}/photos")
async def delete_photo(review_id: str, photo_url: str, current_user=Depends(get_current_verified_user)):
    db      = get_db()
    user_id = str(current_user["_id"])
    try:
        review = await db[COLLECTION].find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review or review["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized.")
    if photo_url not in review.get("photos", []):
        raise HTTPException(status_code=404, detail="Photo not found.")
    await delete_file(photo_url)
    await db[COLLECTION].update_one({"_id": review["_id"]}, {"$pull": {"photos": photo_url}, "$set": {"updated_at": datetime.utcnow()}})
    return {"message": "Photo removed."}


# ── POST toggle helpful ───────────────────────────────────────────────────────
@router.post("/{review_id}/helpful")
async def toggle_helpful(review_id: str, current_user=Depends(get_current_verified_user)):
    db      = get_db()
    user_id = str(current_user["_id"])
    try:
        review = await db[COLLECTION].find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot mark your own review as helpful.")
    if user_id in review.get("helpful_users", []):
        await db[COLLECTION].update_one({"_id": review["_id"]}, {"$pull": {"helpful_users": user_id}, "$inc": {"helpful_count": -1}})
        return {"helpful": False}
    else:
        await db[COLLECTION].update_one({"_id": review["_id"]}, {"$addToSet": {"helpful_users": user_id}, "$inc": {"helpful_count": 1}})
        return {"helpful": True}


# ── GET single review ─────────────────────────────────────────────────────────
@router.get("/{review_id}")
async def get_review(review_id: str):
    db = get_db()
    try:
        review = await db[COLLECTION].find_one({"_id": ObjectId(review_id), "is_active": True})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    return serialize(review)
