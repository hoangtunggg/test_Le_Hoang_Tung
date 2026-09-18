import asyncio
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

from faker import Faker
from sqlalchemy import func, insert, select

from app.core.security import get_password_hash
from app.db.session import async_session_maker
from app.models.todo import Todo
from app.models.user import User

DEMO_EMAIL = "demo@test.com"
DEMO_PASSWORD = "Demo@123"
TARGET_USERS = max(1, int(os.getenv("SEED_USERS", "100")))
TARGET_TODOS = max(0, int(os.getenv("SEED_TODOS", "1000")))
USER_BATCH_SIZE = max(1, int(os.getenv("SEED_USER_BATCH_SIZE", "500")))
TODO_BATCH_SIZE = max(1, int(os.getenv("SEED_TODO_BATCH_SIZE", "5000")))
RANDOM_SEED = int(os.getenv("SEED_RANDOM_SEED", "0"))


async def seed_db():
    print("Starting database seeding...")
    print(f"Target users: {TARGET_USERS}, target todos: {TARGET_TODOS}")
    start_time = time.time()

    async with async_session_maker() as session:
        # Targets are minimum totals. Existing rows above a target are preserved.
        count_result = await session.execute(select(func.count()).select_from(User))
        user_count = count_result.scalar_one()
        result = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        demo_user = result.scalar_one_or_none()

        if user_count < TARGET_USERS:
            print("Generating password hash...")
            shared_password_hash = get_password_hash(DEMO_PASSWORD)
            user_fake = Faker()
            user_fake.seed_instance(RANDOM_SEED)

        if not demo_user and user_count < TARGET_USERS:
            print(f"Creating demo user: {DEMO_EMAIL}...")
            demo_user = User(
                id=uuid.uuid4(),
                email=DEMO_EMAIL,
                hashed_password=shared_password_hash,
            )
            session.add(demo_user)
            await session.commit()
            await session.refresh(demo_user)
            user_count += 1
            print("Demo user created.")
        elif demo_user:
            print(f"Demo user {DEMO_EMAIL} already exists.")

        if user_count < TARGET_USERS:
            users_to_create = TARGET_USERS - user_count
            print(
                f"Current user count is {user_count}. "
                f"Seeding {users_to_create} more users..."
            )

            # To ensure emails are unique
            existing_emails_result = await session.execute(select(User.email))
            existing_emails = set(existing_emails_result.scalars().all())

            users_batch = []

            for i in range(1, users_to_create + 1):
                email = user_fake.unique.email()
                while email in existing_emails:
                    email = user_fake.unique.email()
                existing_emails.add(email)

                user_id = uuid.uuid4()
                users_batch.append(
                    {
                        "id": user_id,
                        "email": email,
                        "hashed_password": shared_password_hash,
                        "created_at": datetime.now(timezone.utc),
                    }
                )

                if len(users_batch) >= USER_BATCH_SIZE or i == users_to_create:
                    await session.execute(insert(User), users_batch)
                    await session.commit()
                    print(f"Inserted {len(users_batch)} users...")
                    users_batch = []
        else:
            print(f"User target already met with {user_count} users.")

        # Always reload every user so existing users participate in distribution.
        all_users_result = await session.execute(select(User.id).order_by(User.id))
        all_user_ids = list(all_users_result.scalars().all())

        # 3. Seed TODOs evenly across all users with reproducible fake content
        count_result = await session.execute(select(func.count()).select_from(Todo))
        todo_count = count_result.scalar_one()
        todos_to_create = max(0, TARGET_TODOS - todo_count)

        if todos_to_create == 0:
            print(f"TODO target already met with {todo_count} TODOs.")
        else:
            print("Pre-generating fake data pools for high performance...")
            todo_fake = Faker()
            todo_fake.seed_instance(RANDOM_SEED + 1)
            rng = random.Random(RANDOM_SEED)
            titles = [
                todo_fake.sentence(nb_words=rng.randint(3, 8)).rstrip(".")
                for _ in range(2000)
            ]
            descriptions = [todo_fake.text(max_nb_chars=150) for _ in range(2000)]

            total_batches = (todos_to_create + TODO_BATCH_SIZE - 1) // TODO_BATCH_SIZE

            print(
                f"Seeding {todos_to_create} additional TODOs distributed "
                f"across {len(all_user_ids)} users..."
            )

            for batch_offset in range(0, todos_to_create, TODO_BATCH_SIZE):
                batch_started_at = time.time()
                batch_idx = batch_offset // TODO_BATCH_SIZE
                batch_count = min(TODO_BATCH_SIZE, todos_to_create - batch_offset)
                todos_batch = []
                for item_offset in range(batch_count):
                    now = datetime.now(timezone.utc)
                    absolute_offset = todo_count + batch_offset + item_offset
                    todos_batch.append(
                        {
                            "id": uuid.uuid4(),
                            "title": rng.choice(titles),
                            "description": rng.choice(descriptions),
                            "completed": rng.choice([True, False]),
                            "user_id": all_user_ids[
                                absolute_offset % len(all_user_ids)
                            ],
                            "created_at": now,
                            "updated_at": now,
                        }
                    )

                # Perform bulk insert
                await session.execute(insert(Todo), todos_batch)
                await session.commit()

                batch_elapsed = time.time() - batch_started_at
                inserted_count = min((batch_idx + 1) * TODO_BATCH_SIZE, todos_to_create)
                print(
                    f"Batch {batch_idx + 1}/{total_batches} "
                    f"inserted ({inserted_count} new, "
                    f"{todo_count + inserted_count} total). "
                    f"Time: {batch_elapsed:.2f}s"
                )

    end_time = time.time()
    print(f"Database seeding completed in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed_db())
