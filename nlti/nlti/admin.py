import os
import sys

from sqlalchemy import select

from nlti.auth import hash_password
from nlti.database import SessionLocal
from nlti.models import Account


def main() -> None:
    email = os.getenv("NLTI_ADMIN_EMAIL", "").strip().casefold()
    password = os.getenv("NLTI_ADMIN_PASSWORD", "")
    if not email or len(password) < 16:
        print(
            "Set NLTI_ADMIN_EMAIL and a unique NLTI_ADMIN_PASSWORD (at least 16 characters) "
            "in the process environment, then retry.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    with SessionLocal() as db:
        existing = db.scalar(select(Account).where(Account.email == email))
        if existing:
            print("An account with that email already exists; no changes made.", file=sys.stderr)
            raise SystemExit(1)
        db.add(
            Account(
                email=email,
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
            )
        )
        db.commit()
    print(f"Admin account created for {email}.")


if __name__ == "__main__":
    main()
