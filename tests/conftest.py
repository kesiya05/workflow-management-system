import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_app.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


from app import models  # noqa: E402
from app.auth import hash_password  # noqa: E402


@pytest.fixture()
def people(db_session):
    """admin, one manager, two employees (one reports to the manager, one does not)."""
    def make(name, role, manager=None):
        u = models.User(name=name, email=f"{name.lower()}@example.com", password_hash=hash_password("pw12345"),
                        role=role, manager_id=manager.id if manager else None)
        db_session.add(u)
        db_session.commit()
        return u

    admin = make("Admin", "Admin")
    manager = make("Maria", "Manager")
    emp = make("Eli", "Employee", manager)
    other = make("Olga", "Employee")
    return {"admin": admin, "manager": manager, "emp": emp, "other": other}


@pytest.fixture()
def login(client, people):
    def do(key):
        r = client.post("/api/auth/login", json={"email": people[key].email, "password": "pw12345"})
        assert r.status_code == 200
        return {"Authorization": "Bearer " + r.json()["token"]}

    return do
