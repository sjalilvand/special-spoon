from sqlalchemy import select
from app.db.session import SessionLocal
from app.core.security import hash_password
from app.models.user import User, Role, UserStatus

USERNAME = "diag_e2e"
PASSWORD = "DiagPass!2024"
ROLES = ["ORG_MANAGER", "RECEPTION", "COUNSELOR", "TECHNICAL_SUPERVISOR"]

db = SessionLocal()
try:
    u = db.scalar(select(User).where(User.username == USERNAME))
    if u is None:
        u = User(username=USERNAME, display_name="Diag E2E", status=UserStatus.ACTIVE, must_change_password=False)
        u.password_hash = hash_password(PASSWORD)
        for code in ROLES:
            r = db.get(Role, code)
            if r:
                u.roles.append(r)
        db.add(u)
        db.commit()
        print("created")
    else:
        u.password_hash = hash_password(PASSWORD)
        u.status = UserStatus.ACTIVE
        u.must_change_password = False
        codes = {r.code for r in u.roles}
        for code in ROLES:
            if code not in codes and db.get(Role, code):
                u.roles.append(db.get(Role, code))
        db.commit()
        print("updated")
finally:
    db.close()
