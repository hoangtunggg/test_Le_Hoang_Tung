import uuid

from app.core.redis import RedisClient


async def invalidate_todo_list_cache(redis: RedisClient, user_id: uuid.UUID) -> None:
    """Remove every cached todo-list variant belonging to one user."""
    await redis.delete_pattern(f"todos:list:user:{user_id}:*")
