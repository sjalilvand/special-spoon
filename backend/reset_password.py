"""بازنشانی رمز کاربر - در صورت فراموشی.

اجرا:  docker compose run --rm api python reset_password.py --username admin
رمز تصادفی جدید چاپ می‌شود و همه نشست‌های کاربر باطل می‌گردد.
"""
import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import generate_random_password, hash_password
from app.db.session import SessionLocal
from app.models.user import AuthSession, User


def main() -> int:
    parser = argparse.ArgumentParser(description="بازنشانی رمز عبور کاربر")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == args.username.strip().lower()))
        if user is None:
            print("[خطا] کاربر یافت نشد.", file=sys.stderr)
            return 1
        password = generate_random_password()
        user.password_hash = hash_password(password)
        user.must_change_password = True
        user.status = "active"
        user.auth_version += 1
        now = datetime.now(timezone.utc)
        for s in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))).all():
            s.revoked_at = now
        db.commit()
        print("=" * 50)
        print("رمز جدید - فقط یک بار نمایش داده می‌شود:")
        print(f"  username : {user.username}")
        print(f"  password : {password}")
        print("  ورود بعدی تغییر رمز الزامی است.")
        print("=" * 50)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
