"""Create a Mini SOC user from the command line.

Run from the backend/ directory:

    python create_user.py --username analyst --role analyst

The password is prompted interactively (no echo, never a command-line
argument), so it does not show up in shell history or process lists.

Re-running with a username that already exists does nothing and exits
cleanly, so the script is safe to run more than once.
"""

import argparse
import getpass
import sys

from app.database import SessionLocal
from app.models.user import User
from app.utils.password import hash_password

MIN_PASSWORD_LENGTH = 12


def prompt_password() -> str:
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Error: passwords do not match.", file=sys.stderr)
        sys.exit(1)

    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"Error: password must be at least "
            f"{MIN_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        sys.exit(1)

    return password


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a Mini SOC user (password is prompted)."
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Username (default: admin)",
    )
    parser.add_argument(
        "--role",
        default="admin",
        choices=["analyst", "lead", "admin"],
        help="Role (default: admin)",
    )
    args = parser.parse_args()

    db = SessionLocal()

    try:
        existing = db.query(User).filter(
            User.username == args.username
        ).first()

        if existing:
            print(
                f"User '{args.username}' already exists — nothing to do."
            )
            return

        password = prompt_password()

        user = User(
            username=args.username,
            password_hash=hash_password(password),
            role=args.role,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"User created successfully: {user.username} ({user.role})")

    finally:
        db.close()


if __name__ == "__main__":
    main()