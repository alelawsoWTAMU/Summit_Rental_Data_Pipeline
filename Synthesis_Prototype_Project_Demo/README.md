# Synthesis Prototype: Rental Data Pipeline

**Course:** CIDM-6395 Capstone  
**Author:** Alexander J. Lawson  
**Date:** May 2026  
**Tech Stack:** Python 3.12 · Django 6.0.4 · SQLite3 · Plotly 6.7.0

---

## Project Overview

The Rental Data Pipeline transforms the management of a $2M–$3M annual equipment rental portfolio from a "personality-dependent" manual chore into a robust, prescriptive analytics ecosystem. The application automates the consolidation of data from 25 third-party vendors (19 on a weekly cycle, 6 on a monthly cycle), eliminates the administrative bottleneck of a single human filter, and shifts the responsibility of data integrity back to the source — vendors are required to submit clean, structured information through a web portal, ensuring the internal database remains a reliable "Single Source of Truth."

The application code lives in the [`rental_data_pipeline/`](rental_data_pipeline/) subdirectory of this folder.

**To run and test locally**, see the [Quick Start for Graders](#quick-start-for-graders) section — one command prepares the application for review regardless of the current date.

A hosted demo is also available at: [https://cidm-6395-alexander-lawson.onrender.com/login/](https://cidm-6395-alexander-lawson.onrender.com/login/) *(note: the hosted instance may be in a sleep state on first load — local setup is recommended for grading)*

---

## Synthesis: How the Four Pillars Converge

This project is not an isolated software artifact. It is the deliberate convergence of all four MS-CISBA curricular areas into a single, functioning system.

| Pillar | Metaphor | How It Appears in This Project |
|---|---|---|
| **Software Systems (SS)** | The Muscle | Django MVT architecture, role-based views, management commands, OTP authentication system, vendor portal inline editing, SDLC via ADR/PRD documentation. |
| **Business Analytics (BA)** | The Brain | Embedded Plotly analytics dashboard (`/analytics/`) with Cost Over Time chart, Week Comparison tab, vendor compliance overview, and Rent vs. Buy candidate flagging — all served server-side by Django. |
| **Data Management (DM)** | The Skeleton | Normalized SQLite schema with `rental_staging`, `rental_master`, `vendor_audit`, and `EquipmentMarketRate` tables. Django ORM migrations track the full schema evolution across 16 migration files. Staging → Master publish workflow enforces data integrity before any record becomes "official." |
| **Cybersecurity & Networking (CN)** | The Nervous System | `@login_required` on all protected views, `VendorPortalMiddleware` enforcing role-based routing, OTP two-factor authentication (active; code hardcoded to `111111` — no SMTP integration in this demo environment), `external_user` flag separating third-party vendors from internal staff, `@require_POST` on logout to prevent CSRF exposure. |

---

## Application Architecture

```
rental_data_pipeline/
├── manage.py
├── db.sqlite3                      # SQLite database
├── rental_data_pipeline/           # Django settings package
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── rentals/                        # Core application
    ├── models.py                   # RentalStaging, RentalMaster, VendorAudit, EquipmentMarketRate, etc.
    ├── views.py                    # portal_login, vendor_dashboard, weekly_review, analytics_dashboard
    ├── middleware.py               # VendorPortalMiddleware (role-based routing)
    ├── admin.py                    # Django admin customizations + management actions
    ├── management/commands/        # demo_setup, advance_cycle, bulk_submit_vendors, reset_week, check_deadlines, seed_* helpers
    └── migrations/                 # 16 migration files (full schema evolution history)
```

### Key URL Routes

| URL | View | Access |
|---|---|---|
| `/login/` | `portal_login` | Public |
| `/login/verify/` | `verify_otp` | Authenticated (OTP step — active, code is always `111111`) |
| `/vendor/` | `vendor_dashboard` | Vendor role only |
| `/vendor/edit/<id>/` | `vendor_edit_row` | Vendor role only |
| `/review/` | `weekly_review` | Junior Super User only |
| `/analytics/` | `analytics_dashboard` | Junior Super User only |
| `/admin/` | Django Admin | Admin only |

### Database Schema Summary

| Table | Purpose |
|---|---|
| `rental_staging` | Raw vendor submissions — unverified, pending review |
| `rental_master` | Approved "Single Source of Truth" — published after Super User green-light |
| `vendor_audit` | Compliance tracker — who submitted, when, on-time vs. late |
| `EquipmentMarketRate` | Reference table — purchase price, useful life, daily rate thresholds for RvB flagging |
| `VendorCompany` | Vendor profile — company name, contact info, submission cadence (19 weekly / 6 monthly: Christensen Nixon and Davis, Davidson PLC, Lee-Jordan, Morales Allen and Jones, Preston LLC, West Inc) |
| `UserProfile` | Extends Django auth — role (`admin`, `junior_superuser`, `vendor`), `external_user` flag |
| `LoginOTP` | OTP codes for two-factor authentication (active; code hardcoded to `111111` for demo — no email is sent) |

---

## User Roles & Permissions

| Role | Username | Default Landing | Key Permissions |
|---|---|---|---|
| Administrator | `admin` | `/admin/` | Full Django admin access; cannot access `/analytics/` |
| Junior Super User | `junior_super_01` | `/review/` | Weekly review, publish gating, analytics access |
| Vendor (Example) | `vendor_smith_llc` | `/vendor/` | Own equipment table only; no analytics |

### Test Credentials

Login uses two-factor authentication. After entering your username and password, you will be prompted for a 6-digit verification code. For all demo accounts the code is always **`111111`**. No SMTP server is configured — no email is actually sent. The code is hardcoded in the application for demo purposes.

| Role | Username | Password | 2FA Code |
|---|---|---|---|
| Administrator | `admin` | `<redacted>` | `111111` |
| Junior Super User | `junior_super_01` | `<redacted>` | `111111` |
| Vendor (Pending — demo) | `vendor_smith_llc` | `<redacted>` | `111111` |

> Passwords available on request — contact the author.

---

## Setup & Installation

> **Prerequisite:** Python 3.12 must be installed and on your PATH. Download from [python.org](https://www.python.org/downloads/). All commands below are run from the `Synthesis_Prototype_Project_Demo/` directory (where this README lives) unless otherwise noted.

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
```

PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

If script execution is restricted:
```powershell
.\.venv\Scripts\python.exe -m pip install Django==6.0.4
```

### 2. Install dependencies

```bash
pip install -r rental_data_pipeline/requirements.txt
```

Or manually:
```bash
pip install Django==6.0.4 plotly==6.7.0 python-dotenv==1.2.2 apscheduler==3.11.2 pytz==2026.1.post1 whitenoise==6.9.0
```

### 3. Run initial Django setup

```bash
cd rental_data_pipeline
python manage.py migrate
```

### 4. Start the development server

```bash
python manage.py runserver
```

Navigate to `http://127.0.0.1:8000/`

### 5. (Optional- But Recommended) Seed demonstration data

The database (`db.sqlite3`) included in this repository is pre-seeded with Week 1 2026 through Week 17 2026 of actual rental data from `docs/master_ledger_linked_v4.csv` across 25 vendor companies. No additional seeding is required to explore the application.

To regenerate from scratch (wipes and re-seeds weeks 1–17 from the master ledger CSV):
```bash
python manage.py seed_user_schema --csv docs/master_ledger_linked_v4.csv
python manage.py seed_ledger
```

---

## Environment Variables (`.env`)

**No SMTP integration is active in this demo.** As a result:
- No 2FA OTP emails are sent — the verification code is hardcoded to `111111` for all accounts.
- No vendor deadline reminder/nudge emails are sent — the `check_deadlines` command is wired to send them but will silently skip delivery without credentials.

To enable email features, create `rental_data_pipeline/.env` with SMTP credentials:
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=true
SUPERUSER_CC_EMAIL=admin-email@gmail.com
```

---

## Python Package Dependencies

| Package | Version | Purpose |
|---|---|---|
| `Django` | 6.0.4 | Web framework — views, ORM, admin, auth, sessions |
| `plotly` | 6.7.0 | Interactive analytics charts (server-side JSON) |
| `python-dotenv` | 1.2.2 | Loads `.env` at startup |
| `apscheduler` | 3.11.2 | Background scheduler for `check_deadlines` |
| `pytz` | 2026.1.post1 | Timezone support (required by APScheduler) |
| `whitenoise` | 6.9.0 | Serves static files in production (Render deployment) |
| `gunicorn` | 23.0.0 | WSGI server for production deployment (Render) — not needed for local `runserver` |

---

## Project Documentation

All architectural decisions, product requirements, and implementation planning are in the [`../docs/`](../docs/) folder:

| Document Type | Location | Description |
|---|---|---|
| Implementation Plan | [`../docs/Implementation Plan.md`](../docs/Implementation%20Plan.md) | Full feature checklist with UX/testing status |
| ADRs | [`../docs/adr/`](../docs/adr/) | Architectural Decision Records for key design choices |
| PRDs | [`../docs/prd/`](../docs/prd/) | Product Requirement Documents for each feature sprint |
| Briefs | [`../docs/briefs/`](../docs/briefs/) | Weekly project briefs |
| AI Usage Disclosure | [`../docs/AI_Usage_Disclosure.md`](../docs/AI_Usage_Disclosure.md) | Transparency log for AI-assisted development |

---

## Testing the Vendor Submission Workflow

### Submission Window Rules
- The window **opens Monday at midnight** (start of the ISO week).
- The window **closes when the Junior Super User publishes** that week's data to the master ledger via `/review/`. After publish, the Submit button is replaced with a locked "Submission Window Closed" indicator.
- Running `advance_cycle` at the start of any week creates the `VendorAudit` records that open the window.

> **Grading on a Sunday?** ISO weeks run Monday–Sunday, so on a Sunday the vendor portal is still in the current week while the reviewer dashboard has already jumped ahead to the next open cycle. If you want to demo the full vendor → reviewer flow that day, reset the *current* week instead so both sides are aligned. First find today's ISO week number (printed by `demo_setup` on any run, or check the vendor portal header), then run:
> ```bash
> python manage.py demo_setup --reset --no-submit --week <CURRENT_WEEK> --year <YEAR>
> ```
> Then use the **←** navigation arrow on `/review/` to go back to that week. Everything works normally.

---

### Quick Start for Graders

**The database ships with W1–W19 of published master ledger history** (19 weeks of real data). One command calibrates the system to the current week, backfills any unpublished history, and sets up the demo with Smith LLC as the designated pending vendor:

```bash
cd rental_data_pipeline
python manage.py demo_setup --full-reset --backfill
```

This is your starting point every time — no week or year flags needed.

**What the command does:**

1. Reads the current ISO week from the system clock automatically.
2. Publishes every week between W18 and the current week to the master ledger — analytics charts show a continuous history.
3. Hard-wipes any leftover staging/master/audit rows for the current week (vendor uploads, partial runs, etc.) so the state is always clean.
4. Opens the current week's audit cycle with all vendors set to Pending.
5. Bulk-submits all vendors **except Smith LLC**, which is left Pending for the manual vendor demo.
6. Prints credentials and a walkthrough.

**Expected state — the two likely grading weeks (both in May 2026):**

| When you grade | ISO week | Weeks backfilled | Vendors required | After setup |
|---|---|---|---|---|
| Week of May 4 | W19 | — (W19 already current) | **25** (19 weekly + 6 monthly — first week of May) | 24/25 submitted · Smith LLC pending |
| Week of May 11 | W20 | W19 | **19** (weekly only — 6 monthly already covered by W19) | 18/19 submitted · Smith LLC pending |

> **W20 note:** The 6 monthly vendors (Christensen Nixon and Davis, Davidson PLC, Lee-Jordan, Morales Allen and Jones, Preston LLC, West Inc) appear as **Not Required** on the review board — they already submitted earlier in May (W19). This is correct behavior, not a bug. Smith LLC is weekly and behaves identically in both weeks.

The backfill is idempotent — already-published weeks are detected and skipped, so the command is always safe to re-run.

---

### The Grading Flow

Follow these steps in order. The flow is designed so you see the system from the reviewer's perspective first, watch vendor submissions arrive, and then control the publish gate.

#### Step 1 — Initial Setup (run once per session)

```bash
python manage.py demo_setup --full-reset --backfill --no-submit
```

All vendors are now Pending and the cycle is open. `--full-reset` wipes any leftover staging, master, and audit rows before opening — ensuring a completely clean slate regardless of prior runs.

#### Step 2 — Log in as Reviewer (see empty board)

| Field | Value |
|---|---|
| URL | `http://127.0.0.1:8000/login/` |
| Username | `junior_super_01` |
| Password | `<redacted>` |
| 2FA Code | `111111` |

You land on `/review/`. The board shows all vendors as **Pending** with no submission timestamps — this is the start-of-week state a real JSU would see before vendors check in.

#### Step 3 — Simulate Vendor Check-ins (run in a second terminal)

Keep the server running. In a separate terminal:

```bash
cd rental_data_pipeline
python manage.py bulk_submit_vendors
```

This marks **24 of 25 vendors** as submitted, leaving `vendor_smith_llc` pending. Refresh `/review/` — the board updates live.

#### Step 4 — Submit as Vendor

Log out of `junior_super_01`. Log in as the pending vendor:

| Field | Value |
|---|---|
| Username | `vendor_smith_llc` |
| Password | `<redacted>` |
| 2FA Code | `111111` |

You land on `/vendor/`. The dashboard shows Smith LLC's equipment rows for this week. Edit any row if you like (pencil icon), then click **[Submit Week's Data]**. The button becomes a green "Submitted" badge. Log out.

#### Step 5 — Publish as Reviewer

Log back in as `junior_super_01`. The review board now shows **25/25 submitted**. The **[Publish to Master Ledger]** button is active. Click it, confirm, and the week is locked — all staging rows are promoted to the master ledger.

Visit `/analytics/` to see the updated charts: Cost Over Time, Week Comparison, Vendor Compliance, and Rent-vs-Buy flags.

#### Step 6 — Reset and Repeat (optional, unlimited)

To wipe the published week and run the entire flow again from Step 2:

```bash
python manage.py demo_setup --full-reset --no-submit
```

(No `--backfill` needed after the first run — the analytics history is already filled.) Repeat as many times as you like for the same week. To move on to the next week instead, run `demo_setup --full-reset --backfill --no-submit` again — it will detect the newly published week and open the next one.

After running, follow the printed walkthrough — or see the [User Flow Walkthroughs](#user-flow-walkthroughs) section below.

---

### Test Management Commands

#### `demo_setup` — One-shot grading/demo preparation *(recommended)*
Auto-detects the current week, opens the audit cycle if needed, optionally bulk-submits vendors, and prints walkthrough instructions. All flags are optional.

```bash
# Open cycle with all vendors Pending — reviewer sees empty board first (recommended for grading)
python manage.py demo_setup --backfill --reset --no-submit

# Standard setup — current week, vendor_smith_llc left pending (24/25 auto-submitted)
python manage.py demo_setup

# Fill any gap weeks in the analytics history, then prep the current week
python manage.py demo_setup --backfill

# Reset a previously published/tested week, then re-open with all pending
python manage.py demo_setup --reset --no-submit

# Hard-wipe ALL staging, master, and audit rows — all 25 vendors back to Pending
python manage.py demo_setup --full-reset --week <WEEK> --year <YEAR>

# Backfill gaps AND reset/prep the current week in one shot
python manage.py demo_setup --backfill --reset

# Submit ALL vendors (reviewer sees a fully complete board, Publish button active)
python manage.py demo_setup --submit-all

# Target a specific week
python manage.py demo_setup --week <WEEK> --year <YEAR>

# Leave a different vendor pending (24/25 submitted, Brown Group pending)
python manage.py demo_setup --skip vendor_brown_group --week <WEEK> --year <YEAR>
```

**Flag reference:**

| Flag | Effect |
|---|---|
| *(none)* | 24/25 submitted, `vendor_smith_llc` pending |
| `--skip vendor_brown_group` | 24/25 submitted, Brown Group pending |
| `--no-submit` | Cycle opened, all 25 vendors Pending |
| `--full-reset` | Hard-wipe staging + master + audits, all 25 Pending (use when a vendor has uploaded rows but not submitted) |
| `--reset` | Wipe published master rows + reset audits only; staging preserved |
| `--submit-all` | All 25 submitted — Publish button immediately active |
| `--backfill` | Fill any unpublished gap weeks in the analytics history |

#### `reset_week` — Reopen a published week for re-testing
Deletes the current week's published master rows and resets all vendor audit records back to **pending**, without touching staging data. Use this to re-test the full submission → review → publish flow from scratch.

```bash
# Reset the current ISO week (auto-detected)
python manage.py reset_week

# Reset a specific week
python manage.py reset_week --week <WEEK> --year <YEAR>
```

#### `advance_cycle` — Open a new weekly audit cycle
Creates a `VendorAudit` record for every active vendor for the given week, setting all submissions to pending. Called automatically by `demo_setup` when no audit records exist.

Monthly vendors (Christensen Nixon and Davis, Davidson PLC, Lee-Jordan, Morales Allen and Jones, Preston LLC, West Inc) are skipped if they already have an audit row for the current calendar month — so the number of vendors requiring a submission varies by week:

| Week position in month | Expected vendor count |
|---|---|
| First week of the month | 25 (19 weekly + 6 monthly) |
| Second, third, or fourth week | 19 (weekly only — monthly vendors already submitted) |

```bash
# Open the current ISO week
python manage.py advance_cycle

# Open a specific week
python manage.py advance_cycle --week <WEEK> --year <YEAR>
```

---

#### Demo Scenario: Review page with all submissions pending

To see what the JSU review page looks like at the start of a cycle — before any vendor has submitted — reset the current week's audit rows back to pending:

```bash
python manage.py reset_week
```

Then visit `/review/`. All vendors that are **required to submit this week** will appear with **Pending** status and no submitted timestamp. Vendors on a monthly cadence that already submitted earlier in the month will not appear — they are not required to submit again.

To restore the normal demo state (24/25 submitted, Smith LLC pending):

```bash
python manage.py demo_setup
```

#### `bulk_submit_vendors` — Pre-fill vendor submissions
Marks all vendor audit records for the current week as **verified/submitted**, except the designated test vendor (default: `vendor_smith_llc`). Stamps staging rows so they appear on the weekly review page.

```bash
# Submit all vendors except vendor_smith_llc (default)
python manage.py bulk_submit_vendors

# Skip a different vendor
python manage.py bulk_submit_vendors --skip vendor_brown_group

# Target a specific week
python manage.py bulk_submit_vendors --week <WEEK> --year <YEAR>
```

---

### User Flow Walkthroughs

The system has two primary roles relevant to grading. Both flows begin at `/login/` with OTP verification (code is always **`111111`** — no email is sent in this demo).

#### Test Credentials

| Role | Username | Password | 2FA Code |
|---|---|---|---|
| Administrator | `admin` | `<redacted>` | `111111` |
| Junior Super User | `junior_super_01` | `<redacted>` | `111111` |
| Vendor (Pending — demo) | `vendor_smith_llc` | `<redacted>` | `111111` |

> Passwords available on request — contact the author.

> **Note:** 2FA is active but no email is sent — the code is hardcoded to `111111` for all accounts in this demo environment.

---

#### Reviewer Flow — `junior_super_01`

Start here. The reviewer is the primary role in the system — they control the publish gate.

| Step | Action |
|---|---|
| 1 | Start the server: `cd rental_data_pipeline` then `python manage.py runserver` |
| 2 | In a second terminal, run `python manage.py demo_setup --full-reset --backfill --no-submit` |
| 3 | Navigate to `http://127.0.0.1:8000/login/` |
| 4 | Log in: username `junior_super_01` · password `<redacted>` · 2FA code `111111` |
| 5 | Land on `/review/` — all vendors show **Pending** with no submission timestamps |
| 6 | In the second terminal, run `python manage.py bulk_submit_vendors` |
| 7 | Refresh `/review/` — 24 vendors show **Submitted**; Smith LLC remains **Pending** |
| 8 | Log out — proceed to the [Vendor Flow](#vendor-flow) below to submit Smith LLC |
| 9 | <a id="reviewer-step-9"></a>Log back in as `junior_super_01` — all 25 vendors now show **Submitted** |
| 10 | Click **[Publish to Master Ledger]** — staging rows are promoted to master; week is locked |
| 11 | Visit `/analytics/` to see updated charts: Cost Over Time, Week Comparison, Vendor Compliance, Rent-vs-Buy |
| 12 | **To reset and repeat:** run `python manage.py demo_setup --full-reset --no-submit` then go back to step 3 |

---

<a id="vendor-flow"></a>

#### Vendor Flow — `vendor_smith_llc`

Run this between Reviewer Flow steps 8 and 9.

| Step | Action |
|---|---|
| 1 | Navigate to `http://127.0.0.1:8000/login/` |
| 2 | Log in: username `vendor_smith_llc` · password `<redacted>` · 2FA code `111111` |
| 3 | Land on `/vendor/` — the **Vendor Dashboard** showing Smith LLC's equipment rows for this week |
| 4 | Click the pencil icon on any row to edit it inline (rate, dates, PO number, etc.) — or skip editing |
| 5 | Click **[Submit Week's Data]** — the button becomes a green "Submitted" badge |
| 6 | Log out and return to [Reviewer Flow step 9](#reviewer-step-9) |

The `VendorPortalMiddleware` enforces that vendor accounts can only reach `/vendor/` routes — attempting to access `/review/` or `/analytics/` redirects them back to their dashboard.

---

### Full-Cycle Reset & Repeat

After publishing a week (end of step 10 in the Reviewer Flow), the week is locked. To wipe it and run the entire flow again from scratch for the same week:

```bash
python manage.py demo_setup --full-reset --no-submit
```

To advance to the next week instead (closing the current one and opening the next):

```bash
python manage.py demo_setup --full-reset --backfill --no-submit
```

Both commands leave all vendors as Pending so you start the reviewer-first flow from the beginning. Repeat as many times as needed.
