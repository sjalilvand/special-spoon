"""فرمان امن ایجاد مدیر اولیه - بند ۴.۲ سند

اجرا:
    docker compose run --rm api python create_admin.py

رمز تصادفی فقط یک بار در خروجی چاپ می‌شود؛ هیچ رمز ثابتی در کد یا Docker وجود ندارد.
"""
import argparse
import sys

from sqlalchemy import select

from app.core.security import generate_random_password, hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User, UserStatus


def main() -> int:
    parser = argparse.ArgumentParser(description="ایجاد مدیر اولیه سامانه")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--display-name", default="مدیر سامانه")
    args = parser.parse_args()

    username = args.username.strip().lower()

    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.username == username)) is not None:
            print(f"[خطا] نام کاربری '{username}' از قبل وجود دارد.", file=sys.stderr)
            return 1

        admin_role = db.get(Role, "SYSTEM_ADMIN")
        if admin_role is None:
            print("[خطا] نقش SYSTEM_ADMIN یافت نشد؛ ابتدا Migration را اجرا کنید.", file=sys.stderr)
            return 1

        password = generate_random_password()
        user = User(
            username=username,
            display_name=args.display_name,
            status=UserStatus.ACTIVE,
            must_change_password=True,
        )
        user.password_hash = hash_password(password)
        user.roles.append(admin_role)
        db.add(user)
        db.commit()

        print("=" * 50)
        print("مدیر اولیه ایجاد شد - این اطلاعات فقط یک بار نمایش داده می‌شود:")
        print(f"  username : {username}")
        print(f"  password : {password}")
        print("  رمز را در جای امن ذخیره کنید؛ در ورود بعدی تغییر رمز الزامی است.")
        print("=" * 50)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
