# Capstone Implementation Plan: Equipment Rental Data Pipeline
**Date:** April 11, 2026  
**Project Lead:** Alexander J. Lawson  
**System Architecture:** Django / SQL / Plotly (embedded analytics tab)

---

## 1. Data Sanitization & Seeding
* ✅ **Scrubbing Protocol:** Replace all proprietary company identifiers with generic placeholders.
* ✅ **Dummy Data Generation:** Create a CSV/JSON seed file containing 100+ active rental lines across 25 vendors to test the "Initial State" of the database.

## 2. User Authentication & Permissions Logic
| Profile Type | Permission Tier | Functional Responsibility |
| :--- | :--- | :--- |
| **Administrator** | Access Control | User/Group management and admin configuration in Django admin. |
| **Super User (x2)** | Operational Approver | Weekly review, publish gating, delinquent vendor resolution, and analytics consumption via `/review/` and `/analytics/`. |
| **Viewer** | Read-Only Observer | Analytics access only via `/analytics/`. Cannot access `/review/`, `/vendor/`, or `/admin/`. Represents an internal company stakeholder — a department manager or executive who needs visibility into spend data but has no role in the data intake or approval workflow. *(Documented as a role concept; not implemented in this capstone. In a production deployment, access would be restricted to users authenticating from the company's own email domain — no outside access.)* |
| **Vendor (x25)** | Provider | Access restricted to their own "Company Suite" only. |

* ✅ **Identity Flags:** Internal users (admin + 2 junior super users) are treated as staff accounts; vendor users are non-staff and flagged as third-party (`external_user=True`).

* **Vendor Requirements:**
    * ✅ Access to an editable table for their specific equipment.
    * ✅ **Hard Validation:** Entries must pass date and currency formatting checks.
    * ✅ **Compliance:** Must check "No Changes this week" or update records to submit. `declare_no_change` admin action on VendorAudit records the timestamp and sets `verified = True`.

## 3. Database Schema & Tables
* ✅ **Staging Table (`rental_staging`):** Where raw vendor submissions sit before review.
* ✅ **Production Table (`rental_master`):** The "Single Source of Truth" populated only after Super User approval.
* ✅ **Compliance Table (`vendor_audit`):** Tracks who has logged in, when they submitted, and their "Current Week" status.

## 4. Security & Access
* **MFA / Email OTP *(Implemented but disabled — out of scope for this capstone)* (2026-04-23):** A full email-based two-factor authentication system was built: `LoginOTP` model (migration 0014), `portal_login` step-1 view issuing a 6-digit CSPRNG code via `secrets.randbelow`, `verify_otp` step-2 view validating the code, and `verify_otp.html` template. OTPs expire in 10 minutes and are single-use. The Gmail SMTP app-password used for delivery became unstable in the demo environment, causing login to be blocked for all users. The feature is fully preserved in code but the OTP flow is bypassed in `portal_login` — users are authenticated directly after valid credentials. Declared out of scope for this capstone; see Section 10 for re-enablement path.
* ✅ **Unified Login Flow:** All roles authenticate through `/login/`, then route by role: Admin → `/admin/`, Junior Super User → `/review/`, Vendor → `/vendor/`.

## 5. The Operational "Vendor Push" Flow
### A. The Intake Cycle
* ✅ **Weekly vs. Monthly:** Vendors are tagged by cadence. High-volume vendors (Weekly) must verify data by **Thursday at 2:00 PM CST**. Monthly vendors by last day of month at 14:00 CST. Cadence tracked on `VendorAudit`.
* ✅ **Automated Nudging:** The `check_deadlines` management command scans `vendor_audit` at the deadline.
    * If `verified == False` past cutoff, an SMTP email is triggered to the vendor.
    * **CC Logic:** The email is CC'd to the Super User (`SUPERUSER_CC_EMAIL` env var).
    * Supports `--dry-run` and `--cycle-date` flags. Credentials sourced from environment variables.
    * Run: `python manage.py check_deadlines [--dry-run]`
* ✅ **Asset Logic:** `EquipmentMarketRate` reference table added. Stores purchase price, useful life, market daily rate, and RvB daily threshold per equipment type. `rental_master.rvb_candidate` flag is set at publish time via threshold comparison.

### B. The Approval Cycle
* ✅ Super Users access the **Master Consolidation View**.
* ✅ They "Green Light" the week’s data, which triggers a bulk transfer from `staging` to `master`.

### C. The Analytics Brain
* **Decision (2026-04-12):** All analytics are delivered in-house via an embedded Plotly analytics tab served by Django at `/analytics/`. No external BI tooling (e.g. Power BI) is used. Plotly is the final and only analytics solution for this project.
* ✅ **`/analytics/` Tab (2026-05-19):** Role-scoped Django view reads `rental_master` and `vendor_audit` via ORM and renders interactive Plotly charts:
    * Bar chart: Total on-rent spend by vendor and period.
    * Stacked bar: Vendor submission compliance (Verified / Late / Pending) by cycle.
    * Bar chart: Equipment category utilization (top 15 by active quantity).
    * Flag table: Rent-vs-buy candidates (top 25 by daily cost, with live `rvb_candidate` flag).
* ✅ **Role Scoping:** Vendor users are blocked from `/analytics/` entirely (HTTP 403). Analytics access is restricted to Junior Super Users.
* ✅ **Cost Over Time Tab (2026-04-19):** First default tab on analytics dashboard. Plotly line+fill chart showing weekly cost totals from `rental_master`. Auto-summary paragraph compares last two visible periods with % change and severity context.
    * Period toggle (Day / Week / Month / Quarter / Year) scales all cost values client-side.
    * Visible Periods slider filters the number of trailing data points shown; summary recalculates from the visible window.
* ✅ **Week Comparison Tab (2026-04-19):** Side-by-side tables showing equipment that was **Placed On-Rent** vs **Taken Off Rent** between the two most recent published weeks. Count summary and plain-language heading. Backend computes diff via Python set operations on `(vendor_name, equipment_id)` keys.
* ✅ **Seed Data — W16 (2026-04-19):** `seed_w16` management command generates a realistic Week 16 dataset derived from W15 with ~10% equipment dropout and 10 new lines across 6 fictional vendor companies. All company names use placeholder identities from the `VendorCompany` table — no real company names appear in seed data.

---

## 5D. Next Phase — Vendor Data Integrity Verification (W17)

Week 17 (2026-04-21 cycle) will be used to test a range of vendor submission scenarios against the full intake and approval pipeline. The goal is to verify that staging validation, audit compliance tracking, and publishing logic all behave correctly under realistic mixed conditions.

### Planned W17 Scenarios
| # | Scenario | Vendor(s) | Expected Outcome |
| :--- | :--- | :--- | :--- |
| S-01 | Normal submission — no changes from W16 | 3–4 vendors | `no_change=True`; audit verified; staging rows cloned |
| S-02 | New equipment added mid-week | 1–2 vendors | New staging rows appear; pass validation; publishable |
| S-03 | Equipment taken off-rent (end date set) | 1–2 vendors | Row present in staging with `on_rent_end` set; reflected in Week Comparison tab after publish |
| S-04 | Rate change on existing line | 1 vendor | Staging row with updated `rate_daily`; diff visible in analytics after publish |
| S-05 | Validation failure (bad date / missing rate) | 1 vendor | Row created in staging with `is_validated=False` and `validation_errors` populated; blocked from publish |
| S-06 | Late submission (past Thursday 2 PM cutoff) | 1 vendor | `is_late=True` on audit; nudge triggered by `check_deadlines` |
| S-07 | Non-submission / no response | 1 vendor | Audit row remains `verified=False`; Late badge shown on `/review/`; shows in `check_deadlines` output |
| S-08 | Duplicate equipment ID submitted | 1 vendor | Duplicate detected; validation error or admin flag |

### Acceptance Criteria for W17 Phase
- All S-01 through S-08 scenarios can be exercised through the existing UI or management commands without code changes.
- Week Comparison tab on `/analytics/` correctly identifies W17 additions and removals relative to W16.
- `/review/` stat cards and vendor badges accurately reflect mixed compliance state across all 8 scenarios.
- `check_deadlines` correctly identifies S-06 and S-07 vendors when run against the W17 cycle date.

---

## 6. UX / Testing Checklist

Status key: ✅ Verified · ⬜ Pending · 🔄 Partial

### 6.1 Authentication & Access Control
| # | User Action / Scenario | Role | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| A-01 | Log in with valid admin credentials | Admin | ✅ | Logs in via `/login/`; `_default_home_for_user` → `/admin/`; 2FA bypassed (see ADR 2026-04-24) |
| A-02 | Log in with valid junior super user credentials | Junior Super User | ✅ | Logs in via `/login/`; `_default_home_for_user` → `/review/`; 2FA bypassed |
| A-03 | Log in with valid vendor credentials | Vendor | ✅ | Logs in via `/login/`; `_default_home_for_user` → `/vendor/`; 2FA bypassed |
| A-04 | Attempt to access `/admin/` as junior super user | Junior Super User | ✅ | `VendorPortalMiddleware` confirmed: junior_superuser → `redirect("/review/")` |
| A-05 | Attempt to access `/admin/` as vendor | Vendor | ✅ | `VendorPortalMiddleware` confirmed: vendor → `redirect("/vendor/")` |
| A-06 | Attempt to access `/vendor/` as admin | Admin | ✅ | `vendor_dashboard`: `if not profile or profile.role != "vendor"` → `redirect("/admin/")` |
| A-07 | Attempt to access `/analytics/` as vendor | Vendor | ✅ | `analytics_dashboard`: `if _is_vendor(user)` → `HttpResponseForbidden` |
| A-08 | Attempt to access `/review/` as vendor | Vendor | ✅ | `weekly_review`: `if profile.role != "junior_superuser"` → `redirect("/admin/")` |
| A-11 | Attempt to access `/analytics/` as admin | Admin | ✅ | `analytics_dashboard`: admin role != junior_superuser → `HttpResponseForbidden` |
| A-09 | Sign out from any page | All | ✅ | `portal_logout` is `@require_POST`; calls `logout()`; redirects to `/login/` |
| A-10 | Access any page while unauthenticated | — | ✅ | `@login_required` on all protected views; `LOGIN_URL = '/login/'` in settings |
| A-12 | Enter valid OTP at `/login/verify/` | All | N/A | 2FA disabled for this capstone — OTP code preserved but flow bypassed |
| A-13 | Enter invalid OTP at `/login/verify/` | All | N/A | 2FA disabled for this capstone |
| A-14 | OTP expires after 10 minutes | All | N/A | 2FA disabled for this capstone |
| A-15 | Return to login from verify page | All | N/A | 2FA disabled for this capstone |

### 6.2 Vendor Portal
| # | User Action / Scenario | Role | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| V-01 | View own equipment table on dashboard | Vendor | ✅ | `staging_qs = RentalStaging.objects.filter(vendor_name=company_name)` — scoped by authenticated user's company |
| V-02 | Double-click a row to activate inline edit | Vendor | ⬜ | Row cells become inputs |
| V-03 | Edit Equipment ID inline and save | Vendor | ✅ | `vendor_edit_row` validates all fields and saves; confirmed in views.py |
| V-04 | Edit Description, Qty, Monthly Rate inline | Vendor | ✅ | Same `vendor_edit_row` endpoint handles all editable fields |
| V-05 | Cancel inline edit without saving | Vendor | ⬜ | Row reverts to original values |
| V-06 | Delete a row via trash icon | Vendor | ✅ | `vendor_delete_row`: `get(pk=pk, vendor_name=company_name)` — cross-vendor attempt returns 404 |
| V-07 | Add a new row via "Add Row" modal | Vendor | ✅ | `vendor_add_row`: validates all required fields; returns 400 with field errors on failure; creates row |
| V-08 | Submit Weekly Report with no changes | Vendor | ✅ | `vendor_declare_no_change` sets `no_change=True` on VendorAudit; warns if already verified |
| V-09 | Submit Weekly Report after editing rows | Vendor | ⬜ | Modal shows record count; `no_change=False` on audit |
| V-10 | Submit a second time in the same week | Vendor | ⬜ | Submit buttons replaced with "✓ Week N Submitted" badge |
| V-11 | View page after already submitted this week | Vendor | ⬜ | Submission badge shown; edit/delete/add remain functional |
| V-12 | Attempt to view another vendor's dashboard URL | Vendor | ✅ | All endpoints (`vendor_edit_row`, `vendor_delete_row`, `vendor_add_row`) scope by `company_name`; pk lookups use `vendor_name` filter — cross-vendor attempt → 404 |

### 6.3 Admin Portal
| # | User Action / Scenario | Role | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| AD-01 | View all staging rows across vendors | Admin | ✅ | `RentalStagingAdmin` with `list_display` and `actions` registered in admin.py |
| AD-02 | Approve (publish) staging rows to master | Admin | ✅ | `publish_to_master` action registered on `RentalStagingAdmin`; skips invalid rows |
| AD-03 | View vendor audit records and compliance status | Admin | ✅ | `VendorAuditAdmin` with `list_display` confirmed in admin.py |
| AD-04 | Reset a vendor user password | Admin | ✅ | Standard Django admin user change form; no custom code required |
| AD-05 | Create a new vendor user and assign company | Admin | ✅ | `UserProfile` and `VendorCompany` registered in admin.py |
| AD-06 | Run `advance_cycle --week N` management command | Admin | ✅ | `advance_cycle.py` confirmed present in `management/commands/` |
| AD-07 | Run `check_deadlines` management command | Admin | ✅ | `check_deadlines.py` confirmed present in `management/commands/` |
| AD-08 | Run `seed_rental_data` management command | Admin | ✅ | `seed_rental_data.py` confirmed present in `management/commands/` |
| AD-09 | Use admin topbar Home/Users/Groups links | Admin | ⬜ | Right-cluster nav links function and stay role-focused |
| AD-10 | Verify Users/Groups pages hide breadcrumb strip | Admin | ⬜ | Blue path strip removed on Users/Groups pages only |

### 6.4 Weekly Review Page (`/review/`)
| # | User Action / Scenario | Role | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| R-01 | View current week's vendor breakdown | Junior Super User | ✅ | `weekly_review` loads all `VendorCompany` rows regardless of audit state |
| R-02 | Verify Pending badge shown for unsubmitted vendors | Junior Super User | ⬜ | Vendors with no audit show Pending |
| R-03 | Verify Submitted badge for verified vendors | Junior Super User | ⬜ | `audit.verified=True`, `no_change=False` |
| R-04 | Verify No Changes badge for no-change declarations | Junior Super User | ⬜ | `audit.verified=True`, `no_change=True` |
| R-05 | Verify Late badge for overdue vendors | Junior Super User | ⬜ | `audit.is_late=True` |
| R-06 | Stat cards reflect correct counts | Junior Super User | ⬜ | Total / Submitted / Pending / Late / Not Required match table |
| R-07 | Navigate to previous week via ← arrow | Junior Super User | ✅ | `?week=` param accepted: `int(request.GET.get("week", iso[1]))` in `weekly_review` |
| R-08 | Navigate to next week via → arrow | Junior Super User | ✅ | Same `?week=` query param handling confirmed |
| R-09 | Return to current week via "Today" button | Junior Super User | ⬜ | Removes query params; restores current ISO week |
| R-10 | Download consolidated table as CSV | Junior Super User | ⬜ | CSV matches on-screen table; filename includes week/year |
| R-11 | Consolidated table columns match Excel format | Junior Super User | ⬜ | YEAR, WEEK #, DATE, RENTAL COMPANY, TYPE, EQUIP #, DESC, START, END, PO, SN#, RATE, COMMENTS |
| R-12 | Empty state shown when no staging rows exist | Junior Super User | ⬜ | Graceful empty message; no JS errors |
| R-13 | Publish button advisory when vendors pending | Junior Super User | ✅ | Amber button shown with pending count; blue when all resolved; hard block removed (2026-04-23) |
| R-14 | Published week shows "Go to Week N" shortcut | Junior Super User | ⬜ | Next-week button appears after publish only |
| R-15 | Delinquent vendor shows Use Previous / Exclude buttons | Junior Super User | ✅ | Unverified vendors have resolution buttons in vendor table (2026-04-23) |
| R-16 | Use Previous carries forward prior published data | Junior Super User | ✅ | Most recent RentalMaster rows per equipment_id copied into staging as SUBMITTED (2026-04-23) |
| R-17 | Exclude removes vendor staging rows | Junior Super User | ✅ | Staging rows deleted; VendorAudit marked verified (2026-04-23) |
| R-18 | Publish click auto-prompts delinquent resolution | Junior Super User | ✅ | Sequential resolution modals shown before publish modal opens (2026-04-23) |
| R-19 | Staging integrity errors gray out Confirm & Publish | Junior Super User | ✅ | Disabled button with tooltip when validate endpoint returns errors (2026-04-23) |
| R-20 | TYPE OF EQUIP. column is a dropdown in consolidated table | Junior Super User | ✅ | Double-click opens ApprovedEquipmentCategory select (2026-04-23) |
| R-21 | RENTAL CO. column is a dropdown in consolidated table | Junior Super User | ✅ | Double-click opens VendorCompany select (2026-04-24) |

### 6.5 Analytics Dashboard (`/analytics/`)
| # | User Action / Scenario | Role | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| AN-01 | View spend-by-vendor bar chart | Junior Super User | ✅ | Data aggregated from `RentalMaster` in `analytics_dashboard` view; JSON serialized to template |
| AN-02 | View compliance heatmap / stacked bar | Junior Super User | ✅ | `VendorAudit.objects.all()` with all cycles pulled in view |
| AN-03 | View equipment category utilization chart | Junior Super User | ✅ | Top categories by active quantity queried and passed to template |
| AN-04 | View rent-vs-buy flag table | Junior Super User | ✅ | `rvb_candidate` field queried from `RentalMaster` in view |
| AN-05 | Navigate to Reviewer Portal via topbar button | Junior Super User | ⬜ | Button reads "Reviewer Portal"; goes to `/review/` |
| AN-06 | Attempt analytics access as admin | Admin | ✅ | `analytics_dashboard`: `profile.role != "junior_superuser"` → `HttpResponseForbidden` (admin role blocked) |
| AN-07 | View Cost Over Time chart (default tab) | Junior Super User | ⬜ | Line+fill chart; loads with all periods visible |
| AN-08 | Toggle cost period (Day/Week/Month/Quarter/Year) | Junior Super User | ⬜ | Chart y-axis and summary paragraph update correctly |
| AN-09 | Drag Visible Periods slider to filter chart | Junior Super User | ⬜ | Chart trims to last N points; summary reflects new window |
| AN-10 | View Week Comparison tab | Junior Super User | ⬜ | Two side-by-side tables; Placed On-Rent (green) and Taken Off Rent (red) |
| AN-11 | Verify Week Comparison counts match W16 seed delta | Junior Super User | ⬜ | Should show 10 placed, 77 taken off rent for W15→W16 |

### 6.6 Cross-Cutting Concerns
| # | User Action / Scenario | Status | Notes |
| :--- | :--- | :--- | :--- |
| X-01 | Sign Out POST form works from vendor dashboard | ✅ | `vendor_dashboard.html` line 674–676: `<form method="post" action="{% url 'portal_logout' %}">` + `{% csrf_token %}` |
| X-02 | Sign Out POST form works from analytics page | ✅ | `analytics.html` line 738–740: same pattern confirmed |
| X-03 | Sign Out POST form works from weekly review page | ✅ | `weekly_review.html` line 393–395: same pattern confirmed |
| X-04 | Sign Out POST form works from Django admin | ✅ | `admin/login.html` line 257–258: POST form with `{% csrf_token %}` |
| X-05 | No plaintext credentials in any committed file | ✅ | `EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")`; `.env` in `.gitignore` (root) |
| X-06 | CSRF token present on all POST forms | ✅ | All POST forms in all templates confirmed with `{% csrf_token %}`; `CsrfViewMiddleware` in MIDDLEWARE stack |
| X-07 | Mobile/narrow viewport — topbar does not break | ⬜ | Inspect at 768px width |
| X-08 | Consolidated table horizontal scroll on narrow screen | ⬜ | `overflow-x: auto` on `.table-scroll` |

---

## 7. Phase 1 Completion Summary (2026-04-20)

### ✅ Completed Modules
- **Analytics Dashboard:** Full Plotly dashboard with period toggles, cost/volume over time, week comparison, spend by vendor, compliance tracking, and rent-vs-buy candidates. Searchable filters (department, supplier, category, PO) with datalist autocomplete. Real-time slicer synchronization. PDF export with branded layout and synopsis. Period bucketing fixed for monthly/quarterly/yearly views. Spinner feedback on tab transitions.
- **Admin Portal:** Django admin interface with PODepartment model for PO→mill-department mapping. Equipment categories populated from EquipmentMarketRate. Full CRUD on master rental records, staging submissions, vendor audits, equipment market rates, and PO department assignments.
- **Publish/Consolidation Workflow:** Week consolidation view (`/review/`) with vendor compliance badges, stat cards, and CSV export. Bulk publish from `rental_staging` to `rental_master`. Week navigation and "Go to Next Week" shortcut. All data validation and approval gating in place.

### Current State
- **Database:** 764 distinct POs randomly assigned to 7 mill departments (Coke, Iron, Steel, Plate, Hot Mill, Cold Mill, MEU). 1,695 RentalMaster rows with populated `equipment_category` from market rate lookup. Week 16 seed data complete with realistic vendor/equipment mix.
- **Compliance Tracking:** `VendorAudit` rows support weekly/monthly cadences. `check_deadlines` management command functional with SMTP integration. `no_change` declarations supported.
- **Users:** 1 admin, 2 junior super users, 25 vendor accounts tied to distinct companies. All configured in Django admin.

---

## 8. Phase 2 — Vendor Email Integration & Realistic Data Submission Patterns (2026-04-21 onwards)

### Objective
Simulate a realistic week of vendor submissions by:
1. Generating fake Gmail accounts for all 25 vendor users.
2. Creating authentic SMTP-based email notifications (deadline nudges, confirmation receipts, approval summaries).
3. Populating vendor data throughout the week in realistic patterns (morning submissions, mid-week updates, late submissions, no-change declarations).
4. Enforcing strict data validation rules at each submission point.
5. Demonstrating the full end-to-end compliance pipeline under realistic conditions.

### Phase 2.1 — Fake Email Account Setup

#### Requirements
- **Email Provider:** Gmail API or SMTP forwarding to simulate realistic email delivery.
- **Account Pattern:** Each vendor user (25 total) assigned a fake Gmail address: `vendor_{company_slug}@example.com` (with actual forwarding to a test inbox or mock SMTP handler).
- **Credentials Storage:** Email addresses and credentials stored securely via environment variables (no hardcoding).
- **Notification Types:**
  - Deadline nudge: Sent Thursday 2 PM if vendor hasn't submitted yet (triggered by `check_deadlines`).
  - Submission receipt: Sent immediately after vendor completes "Submit" action from `/vendor/` portal.
  - Late submission warning: Sent if vendor submits after Thursday 2 PM CST.
  - Approval confirmation: Sent to vendor after super user publishes the week (shows final master data snapshot).

#### Implementation Plan
- [ ] Create `EmailAccount` Django model to store fake email addresses, passwords (hashed), and vendor association.
- [ ] Generate 25 fake Gmail accounts via a new management command `generate_vendor_emails`.
  - Each vendor gets a unique email (`vendor_{company_slug}@{DOMAIN}`).
  - Passwords generated securely and stored hashed.
  - SMTP relay configured to forward to a monitored mailbox or mock handler.
- [ ] Wire SMTP credentials into `settings.py` via environment variables (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_FROM_ADDRESS`).
- [ ] Update `check_deadlines` to send real SMTP emails (already scaffolded; wire in EmailAccount lookup).
- [ ] Add post-submission hooks to `vendor_submission_views.py` to send receipt emails.
- [ ] Add post-publish hook to consolidation workflow to broadcast approval emails to all vendors.

### Phase 2.2 — Realistic Vendor Data Submission Patterns

#### Submission Scenarios for Week 17 (2026-04-21–2026-04-25)

| Day | Scenario | Vendor Count | Submission Type | Expected Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Mon (4/21)** | Early birds — submit "no change" | 5–7 | `no_change=True` | Audit verified immediately; no further action needed this week. |
| **Tue (4/22)** | New equipment added | 3–4 | New rows in staging | Validation passes; rows queued for publish. |
| **Wed (4/23)** | Equipment end-dated | 2–3 | Rows with `on_rent_end` set | Triggers "Taken Off Rent" logic. |
| **Thu 10 AM (4/24)** | Rate changes on existing lines | 4–5 | Modified `rate_daily` | Staging rows created; visible in review tab. |
| **Thu 1 PM (4/24)** | Last-minute additions | 2–3 | New equipment mid-week | Still within deadline; marked verified. |
| **Thu 2:15 PM (4/24)** | Late submission | 1–2 | Any submission type | `is_late=True` on audit; nudge already sent. |
| **Fri (4/25)** | No response / non-submission | 1–2 | No activity | Audit remains `verified=False`; appears in review lag list. |
| **Fri 3 PM (4/25)** | Validation failure recovery | 1 vendor | Resubmit with corrected data | First attempt had bad date; resubmit passes validation. |

#### Implementation Plan
- [ ] Create a new management command `simulate_vendor_week` that:
  - Takes a week number and vendor mix as parameters.
  - For each scenario, programmatically creates or updates staging rows via the `RentalStaging` model.
  - Optionally triggers `VendorAudit` verification and "no change" declarations.
  - Simulates submission timestamps throughout the week.
  - Logs all actions for review.
  - Supports `--dry-run` to preview without committing changes.
- [ ] Wire vendor timestamps (`submitted_at`, `no_change_declared_at`) to reflect realistic submission times.
- [ ] Ensure `/review/` page correctly reflects mixed compliance state (Verified / Late / Pending / No Changes).

### Phase 2.3 — Strict Data Validation Rules

#### Validation Layers

| Layer | Rule | Enforcement | Notes |
| :--- | :--- | :--- | :--- |
| **Form-level** | Required fields (Equipment ID, Description, Qty, Rate, Start Date) | Form HTML5 `required` attribute; client-side feedback | User cannot submit incomplete row. |
| **Backend (serializer)** | Date format check (`YYYY-MM-DD`) | Django validators + custom clean methods | Invalid dates reject submission. |
| **Backend (model)** | `on_rent_start <= on_rent_end` OR `on_rent_end` is null | Model `clean()` method | Prevents end-dating before start. |
| **Backend (business)** | `rate_daily > 0` and `quantity > 0` | Model validators | Negative or zero values rejected. |
| **Backend (business)** | No duplicate `(vendor_name, equipment_id)` per week | Query check in view | Same equipment cannot be listed twice by same vendor. |
| **Backend (business)** | Currency must be USD (hardcoded for now) | Model choice field | Allows future multi-currency support. |
| **Staging-to-Master** | All rows in staging must pass `is_validated=True` | `publish_to_master` action check | Cannot publish rows with validation errors. |

#### Implementation Plan
- [ ] Audit existing form and model validators in `RentalStaging` (already mostly complete).
- [ ] Add explicit validation error messages to `validation_errors` field for failed rows (already functional).
- [ ] Wire validation summary to `/review/` page: show count of rows with errors; allow super user to drill in.
- [ ] Create a `validate_staging_batch` management command to re-validate all staging rows for a given week (useful for debugging).
- [ ] Add optional `--strict` flag to `publish_to_master` that aborts if any errors found (default: already skips error rows).

### Phase 2.4 — Email-Driven UX Enhancements

#### Notification Content Templates
- **Deadline Nudge:** "Hi [Vendor Name], this is a reminder that your equipment rental data for Week N is due by Thursday 2:00 PM CST. Please log in to [app URL] and submit your report."
- **Submission Receipt:** "Thank you for submitting your Week N equipment data. Your submission was received on [timestamp] with [X] records. You will receive a confirmation email once the data has been approved."
- **Late Submission Warning:** "Your Week N submission was received after the 2:00 PM CST deadline. It has been marked as late but will still be reviewed for publication."
- **Approval Confirmation:** "Week N data has been published. Your [X] equipment records are now live in the system. [Link to PDF snapshot of master data]."

#### Implementation Plan
- [ ] Create Django email template files (HTML + plaintext) for each notification type.
- [ ] Wire up template context variables (vendor name, week number, timestamp, record counts, download links).
- [ ] Update `check_deadlines`, post-submission hooks, and publish workflow to render and send emails.

### Phase 2.5 — Testing & Acceptance

#### Acceptance Criteria for Phase 2
- [ ] All 25 vendor users have valid fake Gmail addresses configured.
- [ ] `simulate_vendor_week` command successfully populates Week 17 with realistic mixed-submission patterns.
- [ ] `/review/` page correctly reflects all 8 scenario types (early birds, new equipment, late submissions, non-submissions, validation errors, etc.).
- [ ] `check_deadlines` sends SMTP emails to unverified vendors on Thu 2 PM.
- [ ] Submission receipt emails sent immediately upon vendor submit action.
- [ ] Approval confirmation emails sent to all vendors after publish.
- [ ] All validation rules enforce correctly; rows with errors cannot be published.
- [ ] Email templates render correctly with real vendor data (no missing context variables).
- [ ] `/review/` shows validation error count and drill-down detail for troubleshooting.
- [ ] CSV export from `/review/` includes all Week 17 scenarios.
- [ ] Compliance badges (Verified / Late / Pending / No Changes) all render correctly.

#### Manual Testing Workflow
1. Run `simulate_vendor_week --week=17 --mix=realistic` to populate mixed submission scenarios.
2. Navigate to `/review/?week=17` and verify all scenario badges appear.
3. Run `check_deadlines --cycle-date=2026-04-24` to trigger deadline nudges.
4. Review fake email inbox for receipt and nudge emails.
5. Manually publish Week 17 via `publish_to_master` action; verify approval emails sent.
6. Navigate to `/analytics/?week=17` and verify charts reflect new data.
7. Test each validation rule by attempting invalid submissions through the vendor portal.

---

## 9. Session 2026-04-23 — Reminder Email Verification, Data Integrity Testing & Vendor CSV Upload

**Session Date:** April 23, 2026  
**Focus:** Verify SMTP reminder pipeline end-to-end, execute a comprehensive data validation/integrity test sweep, and build CSV upload capability on the vendor portal.

### 9.1 Reminder Email Live Verification

Objective: Confirm that `send_vendor_reminders` (Thursday 2 PM guard) fires correctly against real delinquent vendors and that CC logic and email content are accurate.

| Task | Details |
| :--- | :--- |
| Run `send_vendor_reminders` live (no `--force`) | Confirm Thursday guard passes at 2 PM CST; verify emails land in `rentalpipelineadmin@gmail.com` |
| Inspect email body for each delinquent vendor | Vendor name, cycle week, deadline date, portal URL all correct |
| Verify CC to `SUPERUSER_CC_EMAIL` | Admin inbox receives one CC per delinquent vendor |
| Cross-check against `/review/` Pending badges | Every vendor with a Pending badge should have received a nudge |
| Test `--dry-run` output matches live run recipients | Counts and vendor names align |

### 9.2 Data Validation & Integrity Test Sweep

Objective: Stress-test every validation layer with deliberate bad inputs; confirm that no invalid row can reach `rental_master`.

| # | Status | Test Case | Expected Result |
| :--- | :--- | :--- | :--- |
| DV-01 | ✅ | Submit a row with blank Equipment ID | `vendor_add_row`: `if not eq_id_raw: errors["equipment_id"] = "Equipment ID is required."` — server-side rejection confirmed |
| DV-02 | ✅ | Submit a row with `rate_daily = 0` | `vendor_add_row`: `if rate <= 0: errors["rate_daily"] = "Monthly rate must be greater than zero."` |
| DV-03 | ✅ | Submit a row with negative `rate_daily` | Same `rate <= 0` check covers negative values |
| DV-04 | ✅ | Submit a row with `on_rent_end` before `on_rent_start` | `vendor_add_row` and `vendor_edit_row`: `if end_date < start_date: errors["on_rent_end"] = "End date cannot be before start date."` |
| DV-05 | ✅ | Submit a row with malformed date string | `datetime.date.fromisoformat()` raises `ValueError` → caught → `errors["on_rent_start"] = "Enter a valid date."` |
| DV-06 | ⬜ | Submit the same `(vendor_name, equipment_id)` twice in one week | **Gap:** `vendor_add_row` has no duplicate check; `RentalStaging` has no unique constraint on `(vendor_name, equipment_id)` — second row is created silently |
| DV-07 | ✅ | Attempt to publish a staging batch containing an invalid row | `publish_to_master` admin action exists; designed to skip invalid rows and report skipped items |
| DV-08 | N/A | Run `validate_staging_batch --week N` on a mixed batch | `validate_staging_batch` command does not exist in `management/commands/` |
| DV-09 | N/A | Correct an invalid row in admin, re-run `validate_staging_batch` | Command not implemented — depends on DV-08 |
| DV-10 | ⬜ | Verify all `equipment_category` values in `rental_master` are in approved list | Requires live DB query: `RentalMaster.objects.exclude(equipment_category__in=ApprovedEquipmentCategory.objects.values_list("name", flat=True))` |

### 9.3 Vendor CSV Upload ✅ Complete

Objective: Allow vendors to bulk-upload their equipment list via a CSV file as an alternative to manual row entry.

#### Requirements
- A clearly labeled **"Upload CSV"** button appears on the vendor dashboard alongside the existing Add Row button.
- Clicking the button opens a modal with a file picker and a downloadable CSV template link.
- Uploaded CSV is parsed server-side; each row is validated against the same rules as manual entry.
- Valid rows are inserted as `RentalStaging` records for the current cycle.
- Rows failing validation are **not** inserted; the vendor receives a clear per-row error report in the response.
- Duplicate `(vendor_name, equipment_id)` rows within the upload or against existing staging rows are rejected.
- Upload is limited to 500 rows and 2 MB per file.
- CSV template columns: `equipment_id`, `equipment_description`, `quantity`, `rate_daily`, `on_rent_start`, `on_rent_end` (optional), `po_number` (optional), `equipment_category`, `comments` (optional).

#### Implementation Plan
- ✅ `vendor_csv_upload` view in `views.py` — parses with Python `csv` module; reuses existing validation logic.
- ✅ URL route `/vendor/csv-upload/` (POST only, `@login_required`) registered in `urls.py`.
- ✅ Upload CSV button and modal added to `vendor_dashboard.html`.
- ✅ Downloadable CSV template served via view response.
- ✅ JSON response with `inserted`, `skipped`, and `errors` (per-row); summary displayed inline in modal.

---

## 10. Pre-Submission Remaining Work

The following items, if completed before submission, close the identified gaps between the current A- assessment and an A+. They are listed in order of grading impact.

### 10.1 Automated Test Suite *(highest impact)*
`tests.py` exists but is empty. A minimal test suite covering the access control layer and validation logic would close the single largest gap cited by any grader.

- [ ] **Access control tests** — Use `django.test.Client` to assert:
  - Vendor user hitting `/analytics/` returns 403.
  - Vendor user hitting `/review/` returns 302 → `/admin/`.
  - Junior super user hitting `/admin/` returns 302 → `/review/`.
  - Unauthenticated request to `/vendor/` returns 302 → `/login/`.
  - Admin user hitting `/analytics/` returns 403.
- [ ] **`vendor_add_row` validation tests** — POST to the endpoint with a test client logged in as a vendor user and assert:
  - Blank `equipment_id` → 400 with `errors.equipment_id` in response JSON.
  - `rate_daily = 0` → 400 with `errors.rate_daily`.
  - Negative `rate_daily` → 400 with `errors.rate_daily`.
  - `on_rent_end` before `on_rent_start` → 400 with `errors.on_rent_end`.
  - Malformed date string → 400 with `errors.on_rent_start`.
  - Valid payload from a vendor with no linked company → 400 with `errors.__all__`.
  - Non-vendor user (junior super user) → 403.
- [ ] **Cross-vendor isolation test** — Create two vendor users in different companies; assert that vendor A cannot delete or edit vendor B's `RentalStaging` row (returns 404).
- [ ] Run: `python manage.py test rentals` — all tests pass before submission.

### 10.2 DV-06 Duplicate Row Enforcement
`vendor_add_row` currently allows the same `(vendor_name, equipment_id)` to be added twice with no error. This is the only data-integrity gap identified in the DV sweep.

- [ ] In `vendor_add_row` (views.py), after collecting `eq_id_raw` and `company_name`, add a duplicate check before the `if errors:` guard:
  ```python
  if RentalStaging.objects.filter(vendor_name=company_name, equipment_id=eq_id_raw).exists():
      errors["equipment_id"] = "This Equipment ID already exists in your submission. Use the inline edit to update it."
  ```
- [ ] Update DV-06 in Section 9.2 from ⬜ to ✅ after verifying the check rejects the duplicate.

### 10.3 Manual Browser Walkthrough
Complete the remaining ⬜ items in sections 6.2, 6.3, 6.4, 6.5, and 6.6 using the running dev server. Focus areas:

- **6.2 Vendor Portal:** V-02 (double-click inline edit), V-05 (cancel reverts row), V-09 (submit after edits), V-10 (second-submit badge), V-11 (page state after submission).
- **6.3 Admin Portal:** AD-09 (topbar nav links), AD-10 (breadcrumb strip on Users/Groups pages).
- **6.4 Weekly Review:** R-02 through R-06 (badges + stat cards), R-09 (Today button), R-10 (CSV download), R-11 (column alignment), R-12 (empty state), R-14 (Go to Next Week button).
- **6.5 Analytics:** AN-05 (Reviewer Portal button), AN-07 through AN-11 (chart tabs and period controls).
- **6.6 Cross-Cutting:** X-07 (topbar at 768px), X-08 (table horizontal scroll).
- **9.2:** DV-10 — run in Django shell: `RentalMaster.objects.exclude(equipment_category__in=ApprovedEquipmentCategory.objects.values_list("name", flat=True))` and confirm the queryset is empty.
- Mark each verified item ✅ in this plan as you go.

---

## 11. Future Enhancements (Post-Capstone)
- **2FA Re-enablement:** The full email OTP flow is built and preserved in `views.py` (`portal_login`, `verify_otp`), `models.py` (`LoginOTP`), and `verify_otp.html`. To re-enable: in `portal_login`, remove the direct `auth_login` call and restore the OTP generation/email block. Requires a stable Gmail app password or an alternative SMTP provider (e.g. SendGrid, AWS SES).
- **Viewer Role Implementation:** Add a Viewer permission tier (read-only analytics access) with company-domain authentication enforcement — only users logging in with a verified internal company email domain may access the analytics tab. No outside or vendor users permitted.
- **Multi-Tenant Email:** Support vendor-owned email addresses (not just fake accounts).
- **Audit Logs:** Track all data mutations with user, timestamp, and change details.
- **Workflow Approval States:** Fine-grained publish states (Draft → Review → Approved → Published).
- **Approval Confirmation Email:** Post-publish broadcast to all vendors confirming their records are live. Out of scope for this capstone.
- **Custom Reports:** Additional analytics views (ROI by department, seasonal trends, etc.).
