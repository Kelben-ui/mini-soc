from app.database import SessionLocal
from app.models.user import User
from app.utils.password import hash_password


db = SessionLocal()

try:
    user = User(
        username="admin",
        password_hash=hash_password("AdminPassword123"),
        role="admin",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    print(f"User created successfully: {user.username}")

finally:
    db.close()
