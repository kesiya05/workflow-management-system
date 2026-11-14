"""Create demo users and a few tasks. All passwords are 'demo123'. Demo data only.

    python -m app.seed
"""
from datetime import timedelta

from . import models
from .auth import hash_password
from .db import Base, SessionLocal, engine


def seed(db) -> None:
    if db.query(models.User).count() > 1:
        return
    mk = lambda name, role, mgr=None: models.User(  # noqa: E731
        name=name, email=f"{name.lower()}@example.com", password_hash=hash_password("demo123"), role=role, manager_id=mgr)
    admin = db.query(models.User).filter_by(role="Admin").first() or mk("Admin", "Admin")
    manager = mk("Maria", "Manager")
    db.add_all([admin, manager])
    db.flush()
    staff = [mk("Eli", "Employee", manager.id), mk("Ana", "Employee", manager.id), mk("Olga", "Employee", manager.id)]
    db.add_all(staff)
    db.flush()
    for i, title in enumerate(["Count weekly stock", "Update allergen sheet", "Train new starter", "Clean extraction hood"]):
        db.add(models.Task(title=title, assignee_id=staff[i % 3].id, creator_id=manager.id,
                           due=models.now() + timedelta(days=2 + i)))
    db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        seed(s)
    print("demo users: admin@example.com (Admin, password from ADMIN_PASSWORD or change-me), "
          "maria@example.com, eli@example.com, ana@example.com, olga@example.com (password demo123)")
