# Business requirements

## Problem
A small multi-branch business runs its repetitive work on WhatsApp and paper: who has to do what, who approved which
leave day or purchase, and who knows it was done. Nothing is recorded, approvals get lost, and managers cannot see
what is overdue.

## Goals
1. Every task has one owner, a due date and a status that everyone can see.
2. Requests (leave, expenses, purchases) follow a fixed approval path, and the decision is recorded.
3. People are told when something needs them, so work does not wait unseen.
4. Managers get a weekly view of work done, work overdue and how long approvals take.

## Users and roles
| Role | Can do |
|---|---|
| Employee | See and update own tasks, submit requests, read own notifications |
| Manager | Everything an Employee can, plus create and assign tasks, approve requests from their own team, see reports and the activity log |
| Admin | Everything, plus create users and approve requests above the approval limit |

## Functional requirements
| ID | Requirement |
|---|---|
| FR1 | Users log in with email and password; every API call except login needs a token |
| FR2 | Managers and admins create tasks and assign them to an employee |
| FR3 | Tasks move todo, in progress, done; steps cannot be skipped and done is final |
| FR4 | Any user can submit a leave, expense or purchase request |
| FR5 | A manager can only decide requests from their own team, never their own request |
| FR6 | Requests above 1000 need an Admin |
| FR7 | Assignments, completions and decisions create a notification for the person affected |
| FR8 | Every login and business action is written to an activity log |
| FR9 | Managers see a summary report: tasks by status, overdue, request outcomes, average hours to decision |

## Non-functional requirements
- Passwords are salted and hashed, never stored or logged in plain text.
- A failed email or notification must never block the business action it belongs to.
- The system runs with one command (`docker compose up`) and keeps data in PostgreSQL.
- Behaviour is covered by automated tests that run on every push.

## Out of scope (for this version)
Single sign-on, file attachments, recurring tasks, a mobile app.
