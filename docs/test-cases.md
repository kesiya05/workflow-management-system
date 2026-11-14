# Test cases

All of these run automatically (`pytest -q`) and on every push through GitHub Actions.

| ID | Requirement | Scenario | Expected result | Automated test |
|---|---|---|---|---|
| TC1 | FR1 | Correct and wrong passwords, unknown email | 200 with token / 401 / 401 | `test_login_ok_and_wrong_password` |
| TC2 | FR1 | Call API without token or with a bad token | 401 | `test_endpoints_need_a_token` |
| TC3 | Roles | Manager and employee try to create a user | 403; admin gets 201, duplicate 409, bad email 422 | `test_only_admin_creates_users` |
| TC4 | FR2, FR7 | Manager assigns task | Task created, assignee notified, bad assignee 422, employee 403 | `test_manager_assigns_task_and_employee_is_notified` |
| TC5 | FR2 | Two employees have tasks | Each sees only own, manager sees all | `test_employee_sees_only_own_tasks` |
| TC6 | FR3, FR7 | Move a task through its states | Skipping 409, wrong person 403, done sets completed_at, done is final, creator notified | `test_task_status_rules` |
| TC7 | FR4, FR5 | Manager approves own team request | Approved, requester notified, second decision 409 | `test_manager_approves_own_team_request` |
| TC8 | FR5, FR6 | Self approval, other team, over-limit, employee deciding | All 403; admin can decide; unknown id 404 | `test_approval_rules` |
| TC9 | FR4 | List requests as each role | Employee own, manager own team, admin all | `test_request_visibility` |
| TC10 | FR4 | Invalid kind, empty description, negative amount | 422 each | `test_invalid_request_payload` |
| TC11 | FR8 | Create a task, read the log | login and task_created present; employee 403 | `test_activity_log_records_actions` |
| TC12 | FR8 | Wrong password | login_failed is logged | `test_failed_login_is_logged` |
| TC13 | FR7 | Mark another user's notification read | 404; own works | `test_notification_mark_read_is_private` |
| TC14 | FR9 | Known set of tasks and one 4 hour approval | Report numbers match exactly | `test_report_numbers` |
| TC15 | Security | Hash the same password twice | Different hashes, never plain text, verify works | `test_passwords_are_hashed_and_salted` |
| TC16 | UI | Open the home page | Page served | `test_ui_page_served` |
