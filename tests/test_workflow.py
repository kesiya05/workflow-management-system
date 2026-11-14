from datetime import timedelta

from app import models


def test_login_ok_and_wrong_password(client, people):
    ok = client.post("/api/auth/login", json={"email": "eli@example.com", "password": "pw12345"})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "Employee"
    assert client.post("/api/auth/login", json={"email": "eli@example.com", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "x"}).status_code == 401


def test_endpoints_need_a_token(client, people):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_only_admin_creates_users(client, login):
    body = {"name": "New", "email": "new@example.com", "password": "secret1", "role": "Employee"}
    assert client.post("/api/users", json=body, headers=login("manager")).status_code == 403
    assert client.post("/api/users", json=body, headers=login("emp")).status_code == 403
    assert client.post("/api/users", json=body, headers=login("admin")).status_code == 201
    assert client.post("/api/users", json=body, headers=login("admin")).status_code == 409   # duplicate email
    assert client.post("/api/users", json={**body, "email": "bad"}, headers=login("admin")).status_code == 422


def test_manager_assigns_task_and_employee_is_notified(client, login, people):
    r = client.post("/api/tasks", json={"title": "Count stock", "assignee_id": people["emp"].id}, headers=login("manager"))
    assert r.status_code == 201
    notes = client.get("/api/notifications", headers=login("emp")).json()
    assert any("Count stock" in n["message"] for n in notes)
    assert client.post("/api/tasks", json={"title": "x", "assignee_id": 999}, headers=login("manager")).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "assignee_id": 1}, headers=login("emp")).status_code == 403


def test_employee_sees_only_own_tasks(client, login, people):
    for who in ("emp", "other"):
        client.post("/api/tasks", json={"title": f"for {who}", "assignee_id": people[who].id}, headers=login("manager"))
    mine = client.get("/api/tasks", headers=login("emp")).json()
    assert [t["title"] for t in mine] == ["for emp"]
    assert len(client.get("/api/tasks", headers=login("manager")).json()) == 2


def test_task_status_rules(client, login, people):
    t = client.post("/api/tasks", json={"title": "A", "assignee_id": people["emp"].id}, headers=login("manager")).json()
    url = f"/api/tasks/{t['id']}/status"
    assert client.patch(url, json={"status": "done"}, headers=login("emp")).status_code == 409        # cannot skip a step
    assert client.patch(url, json={"status": "in_progress"}, headers=login("other")).status_code == 403  # not their task
    assert client.patch(url, json={"status": "in_progress"}, headers=login("emp")).status_code == 200
    done = client.patch(url, json={"status": "done"}, headers=login("emp"))
    assert done.status_code == 200 and done.json()["completed_at"]
    assert client.patch(url, json={"status": "todo"}, headers=login("emp")).status_code == 409        # done is final
    assert client.patch("/api/tasks/999/status", json={"status": "done"}, headers=login("emp")).status_code == 404
    creator_notes = client.get("/api/notifications", headers=login("manager")).json()
    assert any("Task finished" in n["message"] for n in creator_notes)


def test_manager_approves_own_team_request(client, login, people):
    r = client.post("/api/requests", json={"kind": "leave", "description": "2 days"}, headers=login("emp")).json()
    d = client.post(f"/api/requests/{r['id']}/decision", json={"approve": True, "comment": "enjoy"}, headers=login("manager"))
    assert d.status_code == 200 and d.json()["status"] == "approved"
    assert any("approved" in n["message"] for n in client.get("/api/notifications", headers=login("emp")).json())
    again = client.post(f"/api/requests/{r['id']}/decision", json={"approve": False}, headers=login("manager"))
    assert again.status_code == 409


def test_approval_rules(client, login, people):
    mine = client.post("/api/requests", json={"kind": "expense", "description": "taxi", "amount": 30}, headers=login("manager")).json()
    assert client.post(f"/api/requests/{mine['id']}/decision", json={"approve": True}, headers=login("manager")).status_code == 403  # own
    theirs = client.post("/api/requests", json={"kind": "expense", "description": "taxi", "amount": 30}, headers=login("other")).json()
    assert client.post(f"/api/requests/{theirs['id']}/decision", json={"approve": True}, headers=login("manager")).status_code == 403  # not their team
    assert client.post(f"/api/requests/{theirs['id']}/decision", json={"approve": True}, headers=login("admin")).status_code == 200
    big = client.post("/api/requests", json={"kind": "purchase", "description": "oven", "amount": 4500}, headers=login("emp")).json()
    assert client.post(f"/api/requests/{big['id']}/decision", json={"approve": True}, headers=login("manager")).status_code == 403  # over limit
    assert client.post(f"/api/requests/{big['id']}/decision", json={"approve": False, "comment": "too dear"}, headers=login("admin")).json()["status"] == "rejected"
    assert client.post("/api/requests/999/decision", json={"approve": True}, headers=login("admin")).status_code == 404
    assert client.post(f"/api/requests/{big['id']}/decision", json={"approve": True}, headers=login("emp")).status_code == 403   # employees cannot decide


def test_request_visibility(client, login, people):
    client.post("/api/requests", json={"kind": "leave", "description": "a"}, headers=login("emp"))
    client.post("/api/requests", json={"kind": "leave", "description": "b"}, headers=login("other"))
    assert len(client.get("/api/requests", headers=login("emp")).json()) == 1
    assert len(client.get("/api/requests", headers=login("manager")).json()) == 1   # only own team
    assert len(client.get("/api/requests", headers=login("admin")).json()) == 2
    assert len(client.get("/api/requests?status=approved", headers=login("admin")).json()) == 0


def test_invalid_request_payload(client, login):
    h = login("emp")
    assert client.post("/api/requests", json={"kind": "holiday", "description": "x"}, headers=h).status_code == 422
    assert client.post("/api/requests", json={"kind": "leave", "description": ""}, headers=h).status_code == 422
    assert client.post("/api/requests", json={"kind": "expense", "description": "x", "amount": -4}, headers=h).status_code == 422


def test_activity_log_records_actions(client, login, people):
    client.post("/api/tasks", json={"title": "A", "assignee_id": people["emp"].id}, headers=login("manager"))
    log = client.get("/api/activity", headers=login("manager")).json()
    assert {"login", "task_created"} <= {a["action"] for a in log}
    assert client.get("/api/activity", headers=login("emp")).status_code == 403


def test_failed_login_is_logged(client, people):
    client.post("/api/auth/login", json={"email": "eli@example.com", "password": "wrong"})
    assert any(a["action"] == "login_failed" for a in _activity(client, people))


def _activity(client, people):
    token = client.post("/api/auth/login", json={"email": people["admin"].email, "password": "pw12345"}).json()["token"]
    return client.get("/api/activity", headers={"Authorization": "Bearer " + token}).json()


def test_notification_mark_read_is_private(client, login, people):
    client.post("/api/tasks", json={"title": "A", "assignee_id": people["emp"].id}, headers=login("manager"))
    n = client.get("/api/notifications", headers=login("emp")).json()[0]
    assert client.post(f"/api/notifications/{n['id']}/read", headers=login("other")).status_code == 404
    assert client.post(f"/api/notifications/{n['id']}/read", headers=login("emp")).json()["read"] is True


def test_report_numbers(client, login, people, db_session):
    h = login("manager")
    for title in ("a", "b", "c"):
        client.post("/api/tasks", json={"title": title, "assignee_id": people["emp"].id}, headers=h)
    tid = client.get("/api/tasks", headers=h).json()[0]["id"]
    client.patch(f"/api/tasks/{tid}/status", json={"status": "in_progress"}, headers=login("emp"))
    client.patch(f"/api/tasks/{tid}/status", json={"status": "done"}, headers=login("emp"))
    late = db_session.get(models.Task, tid + 1)
    late.due = models.now() - timedelta(days=1)
    r = client.post("/api/requests", json={"kind": "leave", "description": "x"}, headers=login("emp")).json()
    req = db_session.get(models.Request, r["id"])
    req.created_at = models.now() - timedelta(hours=4)
    db_session.commit()
    client.post(f"/api/requests/{r['id']}/decision", json={"approve": True}, headers=h)
    rep = client.get("/api/reports/summary", headers=h).json()
    assert rep["tasks_by_status"] == {"todo": 2, "in_progress": 0, "done": 1}
    assert rep["overdue_tasks"] == 1
    assert rep["requests_by_status"]["approved"] == 1
    assert 3.9 <= rep["avg_hours_to_decision"] <= 4.1
    assert rep["tasks_done_per_person"] == {"Eli": 1}
    assert client.get("/api/reports/summary", headers=login("emp")).status_code == 403


def test_ui_page_served(client):
    assert "Workflow Management System" in client.get("/").text
