from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.schemas.schemas import ReviewCreate, ReviewUpdate
from app.core.database import get_db
from app.utils.dependencies import get_current_verified_user, get_admin_user, get_optional_user
from app.utils.files import save_upload_file, delete_file

router = APIRouter(prefix="/reviews", tags=["Reviews"])

MAX_PHOTOS_PER_REVIEW = 5


def serialize_review(r: dict) -> dict:
    r = dict(r)
    r["id"] = str(r["_id"])
    r.pop("_id", None)
    return r


async def recalculate_destination_rating(db, destination_id: str):
    """Recalculate avg_rating and review_count for a destination."""
    pipeline = [
        {"$match": {"destination_id": destination_id, "is_active": True}},
        {"$group": {
            "_id": None,
            "avg_rating": {"$avg": "$rating"},
            "count": {"$sum": 1}
        }}
    ]
    result = await db.reviews.aggregate(pipeline).to_list(1)
    if result:
        avg = round(result[0]["avg_rating"], 2)
        count = result[0]["count"]
    else:
        avg, count = 0.0, 0

    await db.destinations.update_one(
        {"_id": ObjectId(destination_id)},
        {"$set": {"avg_rating": avg, "review_count": count}}
    )


# ─── List reviews for a destination ──────────────────────────────────────────

@router.get("/destination/{destination_id}")
async def list_reviews(
    destination_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    sort: str = "created_at",  # created_at, rating_high, rating_low, helpful
    rating: Optional[int] = None,
):
    db = get_db()
    query: dict = {"destination_id": destination_id, "is_active": True}
    if rating:
        query["rating"] = rating

    sort_map = {
        "rating_high": [("rating", -1)],
        "rating_low": [("rating", 1)],
        "helpful": [("helpful_count", -1)],
        "created_at": [("created_at", -1)],
    }
    sort_order = sort_map.get(sort, [("created_at", -1)])

    skip = (page - 1) * limit
    cursor = db.reviews.find(query).sort(sort_order).skip(skip).limit(limit)
    reviews = [serialize_review(r) async for r in cursor]
    total = await db.reviews.count_documents(query)

    # Rating breakdown
    pipeline = [
        {"$match": {"destination_id": destination_id, "is_active": True}},
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}}
    ]
    breakdown_raw = await db.reviews.aggregate(pipeline).to_list(5)
    breakdown = {str(item["_id"]): item["count"] for item in breakdown_raw}

    return {
        "reviews": reviews,
        "total": total,
        "page": page,
        "pages": -(-total // limit),
        "rating_breakdown": breakdown
    }


# ─── Create review ────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
async def create_review(data: ReviewCreate, current_user=Depends(get_current_verified_user)):
    db = get_db()
    user_id = str(current_user["_id"])

    # Check destination exists
    try:
        dest = await db.destinations.find_one({"_id": ObjectId(data.destination_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid destination ID.")
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found.")

    # One review per user per destination
    existing = await db.reviews.find_one({
        "destination_id": data.destination_id,
        "user_id": user_id,
        "is_active": True
    })
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You have already reviewed this destination. Edit your existing review."
        )

    doc = {
        "destination_id": data.destination_id,
        "destination_name": dest.get("name"),
        "user_id": user_id,
        "user_name": current_user.get("username") or current_user.get("full_name"),
        "user_avatar": current_user.get("avatar_url"),
        "rating": data.rating,
        "title": data.title,
        "body": data.body,
        "visited_on": data.visited_on,
        "photos": [],
        "helpful_count": 0,
        "helpful_users": [],
        "is_active": True,
        "is_verified_visit": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.reviews.insert_one(doc)
    await recalculate_destination_rating(db, data.destination_id)

    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


# ─── Upload photos to review ──────────────────────────────────────────────────

@router.post("/{review_id}/photos")
async def upload_review_photos(
    review_id: str,
    files: List[UploadFile] = File(...),
    current_user=Depends(get_current_verified_user)
):
    db = get_db()
    user_id = str(current_user["_id"])

    try:
        review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your review.")

    current_photos = review.get("photos", [])
    if len(current_photos) + len(files) > MAX_PHOTOS_PER_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_PHOTOS_PER_REVIEW} photos per review."
        )

    uploaded = []
    for file in files:
        path = await save_upload_file(file, subfolder="reviews")
        uploaded.append(path)

    await db.reviews.update_one(
        {"_id": review["_id"]},
        {
            "$push": {"photos": {"$each": uploaded}},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return {"uploaded": uploaded, "message": f"{len(uploaded)} photo(s) added."}


# ─── Update review ────────────────────────────────────────────────────────────

@router.put("/{review_id}")
async def update_review(
    review_id: str,
    data: ReviewUpdate,
    current_user=Depends(get_current_verified_user)
):
    db = get_db()
    user_id = str(current_user["_id"])

    try:
        review = await db.reviews.find_one({"_id": ObjectId(review_id)})
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

    await db.reviews.update_one({"_id": review["_id"]}, {"$set": updates})
    if "rating" in updates:
        await recalculate_destination_rating(db, review["destination_id"])

    updated = await db.reviews.find_one({"_id": review["_id"]})
    return serialize_review(updated)


# ─── Delete review ────────────────────────────────────────────────────────────

@router.delete("/{review_id}")
async def delete_review(review_id: str, current_user=Depends(get_current_verified_user)):
    db = get_db()
    user_id = str(current_user["_id"])
    role = current_user.get("role")

    try:
        review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review["user_id"] != user_id and role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this review.")

    await db.reviews.update_one(
        {"_id": review["_id"]},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    await recalculate_destination_rating(db, review["destination_id"])
    return {"message": "Review deleted."}


# ─── Delete a photo from review ───────────────────────────────────────────────

@router.delete("/{review_id}/photos")
async def delete_review_photo(
    review_id: str,
    photo_url: str,
    current_user=Depends(get_current_verified_user)
):
    db = get_db()
    user_id = str(current_user["_id"])
    try:
        review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review or review["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized.")

    if photo_url not in review.get("photos", []):
        raise HTTPException(status_code=404, detail="Photo not found in this review.")

    await delete_file(photo_url)
    await db.reviews.update_one(
        {"_id": review["_id"]},
        {
            "$pull": {"photos": photo_url},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return {"message": "Photo removed."}


# ─── Mark review as helpful ───────────────────────────────────────────────────

@router.post("/{review_id}/helpful")
async def mark_helpful(review_id: str, current_user=Depends(get_current_verified_user)):
    db = get_db()
    user_id = str(current_user["_id"])

    try:
        review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot mark your own review as helpful.")

    helpful_users = review.get("helpful_users", [])
    if user_id in helpful_users:
        # Toggle off
        await db.reviews.update_one(
            {"_id": review["_id"]},
            {
                "$pull": {"helpful_users": user_id},
                "$inc": {"helpful_count": -1}
            }
        )
        return {"helpful": False}
    else:
        await db.reviews.update_one(
            {"_id": review["_id"]},
            {
                "$addToSet": {"helpful_users": user_id},
                "$inc": {"helpful_count": 1}
            }
        )
        return {"helpful": True}


# ─── Get single review ────────────────────────────────────────────────────────

@router.get("/{review_id}")
async def get_review(review_id: str):
    db = get_db()
    try:
        review = await db.reviews.find_one({"_id": ObjectId(review_id), "is_active": True})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    return serialize_review(review)
