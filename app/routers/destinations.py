from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import re

from app.schemas.schemas import DestinationCreate, DestinationUpdate
from app.core.database import get_db
from app.utils.dependencies import get_current_verified_user, get_admin_user, get_optional_user
from app.utils.files import save_upload_file, delete_file

router = APIRouter(prefix="/destinations", tags=["Destinations"])


def serialize_dest(d: dict) -> dict:
    d = dict(d)
    d["id"] = str(d["_id"])
    d.pop("_id", None)
    return d


# ─── List destinations ────────────────────────────────────────────────────────

@router.get("/")
async def list_destinations(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    country: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort: Optional[str] = "created_at",  # created_at, rating, name
):
    db = get_db()
    query: dict = {"is_active": True}
    if country:
        query["country"] = re.compile(country, re.IGNORECASE)
    if category:
        query["category"] = re.compile(category, re.IGNORECASE)
    if search:
        query["$text"] = {"$search": search}

    sort_map = {
        "rating": [("avg_rating", -1)],
        "name": [("name", 1)],
        "popular": [("review_count", -1)],
        "created_at": [("created_at", -1)],
    }
    sort_order = sort_map.get(sort, [("created_at", -1)])

    skip = (page - 1) * limit
    cursor = db.destinations.find(query).sort(sort_order).skip(skip).limit(limit)
    destinations = [serialize_dest(d) async for d in cursor]
    total = await db.destinations.count_documents(query)

    return {
        "destinations": destinations,
        "total": total,
        "page": page,
        "pages": -(-total // limit)
    }


# ─── Featured destinations ────────────────────────────────────────────────────

@router.get("/featured")
async def featured_destinations():
    db = get_db()
    cursor = db.destinations.find(
        {"is_active": True, "is_featured": True}
    ).sort("avg_rating", -1).limit(6)
    return [serialize_dest(d) async for d in cursor]


# ─── Get by slug ──────────────────────────────────────────────────────────────

@router.get("/slug/{slug}")
async def get_by_slug(slug: str):
    db = get_db()
    d = await db.destinations.find_one({"slug": slug, "is_active": True})
    if not d:
        raise HTTPException(status_code=404, detail="Destination not found.")
    # Increment view count
    await db.destinations.update_one({"_id": d["_id"]}, {"$inc": {"view_count": 1}})
    return serialize_dest(d)


# ─── Get by ID ────────────────────────────────────────────────────────────────

@router.get("/{destination_id}")
async def get_destination(destination_id: str):
    db = get_db()
    try:
        d = await db.destinations.find_one({"_id": ObjectId(destination_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid destination ID.")
    if not d:
        raise HTTPException(status_code=404, detail="Destination not found.")
    await db.destinations.update_one({"_id": d["_id"]}, {"$inc": {"view_count": 1}})
    return serialize_dest(d)


# ─── Create destination (admin) ───────────────────────────────────────────────

@router.post("/", status_code=201, dependencies=[Depends(get_admin_user)])
async def create_destination(data: DestinationCreate):
    db = get_db()
    if await db.destinations.find_one({"slug": data.slug}):
        raise HTTPException(status_code=400, detail="Slug already exists.")

    doc = {
        **data.dict(),
        "photos": [],
        "cover_photo": None,
        "avg_rating": 0.0,
        "review_count": 0,
        "view_count": 0,
        "is_featured": False,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.destinations.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


# ─── Update destination (admin) ───────────────────────────────────────────────

@router.put("/{destination_id}", dependencies=[Depends(get_admin_user)])
async def update_destination(destination_id: str, data: DestinationUpdate):
    db = get_db()
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        return {"message": "Nothing to update."}
    updates["updated_at"] = datetime.utcnow()
    try:
        result = await db.destinations.update_one(
            {"_id": ObjectId(destination_id)}, {"$set": updates}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid destination ID.")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Destination not found.")
    return {"message": "Destination updated."}


# ─── Upload destination photo (admin) ────────────────────────────────────────

@router.post("/{destination_id}/photos", dependencies=[Depends(get_admin_user)])
async def upload_destination_photo(
    destination_id: str,
    file: UploadFile = File(...),
    set_cover: bool = False
):
    db = get_db()
    try:
        oid = ObjectId(destination_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid destination ID.")

    dest = await db.destinations.find_one({"_id": oid})
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found.")

    path = await save_upload_file(file, subfolder="destinations")
    update = {"$push": {"photos": path}, "$set": {"updated_at": datetime.utcnow()}}
    if set_cover or not dest.get("cover_photo"):
        update["$set"]["cover_photo"] = path
    await db.destinations.update_one({"_id": oid}, update)
    return {"photo_url": path, "message": "Photo uploaded successfully."}


# ─── Delete destination (admin) ───────────────────────────────────────────────

@router.delete("/{destination_id}", dependencies=[Depends(get_admin_user)])
async def delete_destination(destination_id: str):
    db = get_db()
    try:
        result = await db.destinations.update_one(
            {"_id": ObjectId(destination_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid destination ID.")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Destination not found.")
    return {"message": "Destination deactivated."}


# ─── Countries list ───────────────────────────────────────────────────────────

@router.get("/meta/countries")
async def get_countries():
    db = get_db()
    countries = await db.destinations.distinct("country", {"is_active": True})
    return sorted(countries)


# ─── Categories list ──────────────────────────────────────────────────────────

@router.get("/meta/categories")
async def get_categories():
    db = get_db()
    categories = await db.destinations.distinct("category", {"is_active": True})
    return sorted(categories)
