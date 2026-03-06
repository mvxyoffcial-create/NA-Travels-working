from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None
db = None


async def connect_db():
    global client, db
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    # Create indexes
    await create_indexes()
    logger.info("Connected to MongoDB successfully.")


async def close_db():
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed.")


async def create_indexes():
    # Users
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username", unique=True, sparse=True)
    await db.users.create_index("google_id", sparse=True)
    await db.users.create_index("verification_token", sparse=True)
    await db.users.create_index("reset_token", sparse=True)

    # Destinations
    await db.destinations.create_index("slug", unique=True)
    await db.destinations.create_index("country")
    await db.destinations.create_index("category")
    await db.destinations.create_index([("name", "text"), ("description", "text")])

    # Reviews
    await db.reviews.create_index("destination_id")
    await db.reviews.create_index("user_id")
    await db.reviews.create_index([("destination_id", 1), ("user_id", 1)], unique=True)

    logger.info("Database indexes created.")


def get_db():
    return db
