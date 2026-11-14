from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import models
from .auth import bootstrap_admin, current_user, hash_password, issue_token, require_roles, verify_password
from .db import Base, SessionLocal, engine, get_db
from .notify import notify, record
from .schemas import DecisionIn, LoginIn, RequestIn, StatusIn, TaskIn, UserIn


@asynccontextmanager
async def lifespan(_app):
    with SessionLocal() as db:
        bootstrap_admin(db)
    yield


app = FastAPI(title="Workflow Management System", lifespan=lifespan)
Base.metadata.create_all(engine)
STATIC = Path(__file__).parent / "static"
APPROVAL_LIMIT = 1000.0   # amounts above this need an Admin
ALLOWED_MOVES = {("todo", "in_progress"), ("in_progress", "done"), ("in_progress", "todo")}


def user_out(u):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "manager_id": u.manager_id}


def task_out(t):
    return {"id": t.id, "title": t.title, "description": t.description, "status": t.status,
            "assignee_id": t.assignee_id, "creator_id": t.creator_id,
            "due": t.due.isoformat() if t.due else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None}


def request_out(r):
    return {"id": r.id, "kind": r.kind, "description": r.description, "amount": r.amount, "status": r.status,
            "requester_id": r.requester_id, "decided_by": r.decided_by, "comment": r.comment,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None}


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


# ---- auth and users -------------------------------------------------------
@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(email=body.email.lower().strip()).first()
    if u is None or not verify_password(body.password, u.password_hash):
        record(db, None, "login_failed", body.email)
        db.commit()
        raise HTTPException(401, "Wrong email or password")
    record(db, u, "login")
    token = issue_token(db, u)
    return {"token": token, "user": user_out(u)}


@app.get("/api/me")
def me(user: models.User = Depends(current_user)):
    return user_out(user)


@app.post("/api/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db), admin: models.User = Depends(require_roles("Admin"))):
    if db.query(models.User).filter_by(email=body.email.lower()).first():
        raise HTTPException(409, "Email already in use")
    if body.manager_id and db.get(models.User, body.manager_id) is None:
        raise HTTPException(422, "manager_id does not exist")
    u = models.User(name=body.name, email=body.email.lower(), password_hash=hash_password(body.password),
                    role=body.role, manager_id=body.manager_id)
    db.add(u)
    record(db, admin, "user_created", f"{u.email} as {u.role}")
    db.commit()
    return user_out(u)


@app.get("/api/users")
def list_users(db: Session = Depends(get_db), _: models.User = Depends(require_roles("Admin", "Manager"))):
    return [user_out(u) for u in db.query(models.User).order_by(models.User.id)]


# ---- tasks ----------------------------------------------------------------
@app.post("/api/tasks", status_code=201)
def create_task(body: TaskIn, db: Session = Depends(get_db), user: models.User = Depends(require_roles("Admin", "Manager"))):
    assignee = db.get(models.User, body.assignee_id)
    if assignee is None:
        raise HTTPException(422, "assignee_id does not exist")
    t = models.Task(title=body.title, description=body.description, assignee_id=assignee.id, creator_id=user.id, due=body.due)
    db.add(t)
    notify(db, assignee, f"New task assigned to you: {t.title}")
    record(db, user, "task_created", f"{t.title} -> {assignee.email}")
    db.commit()
    return task_out(t)


@app.get("/api/tasks")
def list_tasks(status: str | None = None, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    q = db.query(models.Task)
    if user.role == "Employee":
        q = q.filter(models.Task.assignee_id == user.id)
    if status:
        q = q.filter(models.Task.status == status)
    return [task_out(t) for t in q.order_by(models.Task.id)]


@app.patch("/api/tasks/{task_id}/status")
def move_task(task_id: int, body: StatusIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    t = db.get(models.Task, task_id)
    if t is None:
        raise HTTPException(404, "Task not found")
    if user.role == "Employee" and t.assignee_id != user.id:
        raise HTTPException(403, "Not your task")
    if (t.status, body.status) not in ALLOWED_MOVES:
        raise HTTPException(409, f"Cannot move a task from {t.status} to {body.status}")
    t.status = body.status
    t.completed_at = models.now() if body.status == "done" else None
    record(db, user, "task_status", f"#{t.id} {body.status}")
    if body.status == "done" and t.creator_id != user.id:
        notify(db, db.get(models.User, t.creator_id), f"Task finished: {t.title}")
    db.commit()
    return task_out(t)


# ---- approval requests ----------------------------------------------------
@app.post("/api/requests", status_code=201)
def submit_request(body: RequestIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    r = models.Request(kind=body.kind, description=body.description, amount=body.amount, requester_id=user.id)
    db.add(r)
    db.flush()
    approver = db.get(models.User, user.manager_id) if user.manager_id else None
    if approver is None or body.amount > APPROVAL_LIMIT:
        approver = db.query(models.User).filter_by(role="Admin").first() if approver is None or body.amount > APPROVAL_LIMIT else approver
    if approver:
        notify(db, approver, f"{user.name} asked for approval: {r.kind} {r.amount:.2f}")
    record(db, user, "request_submitted", f"#{r.id} {r.kind} {r.amount}")
    db.commit()
    return request_out(r)


@app.get("/api/requests")
def list_requests(status: str | None = None, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    q = db.query(models.Request)
    if user.role == "Employee":
        q = q.filter(models.Request.requester_id == user.id)
    elif user.role == "Manager":
        report_ids = [u.id for u in db.query(models.User).filter_by(manager_id=user.id)]
        q = q.filter(models.Request.requester_id.in_(report_ids + [user.id]))
    if status:
        q = q.filter(models.Request.status == status)
    return [request_out(r) for r in q.order_by(models.Request.id)]


@app.post("/api/requests/{request_id}/decision")
def decide(request_id: int, body: DecisionIn, db: Session = Depends(get_db),
           user: models.User = Depends(require_roles("Admin", "Manager"))):
    r = db.get(models.Request, request_id)
    if r is None:
        raise HTTPException(404, "Request not found")
    if r.status != "pending":
        raise HTTPException(409, f"Already {r.status}")
    if r.requester_id == user.id:
        raise HTTPException(403, "You cannot decide your own request")
    requester = db.get(models.User, r.requester_id)
    if user.role == "Manager" and requester.manager_id != user.id:
        raise HTTPException(403, "You can only decide requests from your own team")
    if r.amount > APPROVAL_LIMIT and user.role != "Admin":
        raise HTTPException(403, f"Amounts above {APPROVAL_LIMIT:.0f} need an Admin")
    r.status = "approved" if body.approve else "rejected"
    r.decided_by, r.decided_at, r.comment = user.id, models.now(), body.comment
    notify(db, requester, f"Your {r.kind} request was {r.status}" + (f": {body.comment}" if body.comment else ""))
    record(db, user, f"request_{r.status}", f"#{r.id}")
    db.commit()
    return request_out(r)


# ---- notifications, activity, reports ------------------------------------
@app.get("/api/notifications")
def my_notifications(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    rows = db.query(models.Notification).filter_by(user_id=user.id).order_by(models.Notification.id.desc()).limit(50)
    return [{"id": n.id, "message": n.message, "read": n.read, "created_at": n.created_at.isoformat()} for n in rows]


@app.post("/api/notifications/{nid}/read")
def mark_read(nid: int, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    n = db.get(models.Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    n.read = True
    db.commit()
    return {"id": n.id, "read": True}


@app.get("/api/activity")
def activity(db: Session = Depends(get_db), _: models.User = Depends(require_roles("Admin", "Manager"))):
    rows = db.query(models.Activity).order_by(models.Activity.id.desc()).limit(100)
    return [{"at": a.at.isoformat(), "user_id": a.user_id, "action": a.action, "detail": a.detail} for a in rows]


@app.get("/api/reports/summary")
def report(db: Session = Depends(get_db), _: models.User = Depends(require_roles("Admin", "Manager"))):
    tasks = db.query(models.Task).all()
    by_status = {s: 0 for s in ("todo", "in_progress", "done")}
    for t in tasks:
        by_status[t.status] += 1
    overdue = [t for t in tasks if t.due and t.status != "done" and t.due < models.now()]
    reqs = db.query(models.Request).all()
    req_status = {s: 0 for s in ("pending", "approved", "rejected")}
    for r in reqs:
        req_status[r.status] += 1
    decided = [(r.decided_at - r.created_at).total_seconds() / 3600 for r in reqs if r.decided_at]
    done_per_person: dict[str, int] = {}
    for t in tasks:
        if t.status == "done":
            name = db.get(models.User, t.assignee_id).name
            done_per_person[name] = done_per_person.get(name, 0) + 1
    return {"tasks_by_status": by_status, "overdue_tasks": len(overdue), "requests_by_status": req_status,
            "avg_hours_to_decision": round(sum(decided) / len(decided), 2) if decided else None,
            "tasks_done_per_person": done_per_person}
