# Presentation Script — Rental Data Pipeline: Synthesis Prototype
**CIDM-6395 Capstone | Alexander J. Lawson | May 2026**

> **Target runtime:** 10–13 minutes (each slide = ~1 minute of speaking unless noted)
> **Recording note:** Read naturally — pause between sentences. Advance the slide whenever you see `[ADVANCE]`.

---

## SLIDE OUTLINE

| # | Slide Title | Visual |
|---|---|---|
| 1 | Title | Project name, author, course |
| 2 | The Problem | Before/After diagram top half only ("Before") |
| 3 | The Solution | Before/After diagram full ("After") |
| 4 | The Four Pillars | Synthesis pillar table (organism metaphors) |
| 5 | How the Pillars Connect | 4-step data flow cycle |
| 6 | Demo: Secure Login & 2FA | Login Page.png + 2FA Prompt.png |
| 7 | Demo: Vendor Portal | Vendor Data.png + Weekly Checkin Y-N to changes.png + Confirm.png + Success Ribbon.png |
| 8 | Demo: Reviewer Portal | Review Before Data Uploaded.png + Confirm.png (JSU/Review) + Ribbon.png |
| 9 | Demo: Analytics — Spend Over Time | Cost Over Time.png |
| 10 | Demo: Analytics — Weekly Comp & Raw Ledger | Week Comp.png + Raw Ledger.png |
| 11 | Demo: Analytics — Compliance & Rent v. Buy | Compliance.png + Rent v Buy.png |
| 12 | The Fully Realized Vision | Bullet list (no screenshot needed) |
| 13 | Synthesis Reflection | Four-pillar table with "remove any pillar" callout |
| 14 | Conclusion / Thank You | Clean close slide |

---

---

## SLIDE 1 — TITLE

**Slide content:**
- Title: "Summit Equipment Rental Data Pipeline"
- Subtitle: "A Synthesis Prototype — CIDM-6395 Capstone"
- Your name: Alexander J. Lawson
- Date: May 2026
- Institution: West Texas A&M University

**Script (~30 seconds):**

> Hello, my name is Alexander Lawson. This presentation covers the Summit Rental Data Pipeline — the synthesis prototype artifact I produced for CIDM-6395 Capstone at West Texas A&M University. The goal of this recording is to walk you through what the application does, demonstrate the key user flows, and explain how it serves as a concrete proof of the interdependence of the four pillars of the MS CISBA curriculum: Software Systems, Business Analytics, Data Management, and Cybersecurity and Networking. I'll close by forecasting what a fully realized, production version of this system would look like.

`[ADVANCE]`

---

## SLIDE 2 — THE PROBLEM

**Slide content:**
- Heading: "The Problem"
- Visual: The **top half** of the Before/After diagram — showing the old workflow: Excel → Power Automate → Email → Data Integrity Check → C# script → SQL → Power BI
- Key callout bullets:
  - $2M–$3M annual equipment rental portfolio
  - 25+ third-party vendors across the country
  - Data collection relied on a single person, a spreadsheet template, and manual email follow-up
  - Any absence, turnover, or error in that pipeline corrupted the entire analytical foundation

**Script (~75 seconds):**

> The problem this project addresses is one I've lived with professionally for years. Our organization manages a two to three million dollar annual equipment rental portfolio — roughly 25 or more vendors supplying everything from pickup trucks to railroad rail cars to heavy construction equipment. Every week, someone i.e. myself, had to manually email a spreadsheet template to each vendor, collect the responses and consolidate them into a single spreadsheet, run a data integrity check, upload the results through a C# script into a SQL table, and then build a Power BI report on top of it. You can see the old pipeline on this slide. While it does"work" there is an obvious need for improvement and lower overhead

> The critical failure point of that system is that it was completely personality-dependent. If the person who maintained it was unavailable, the data didn't get collected. If a vendor responded with bad formatting and the human-filter did not catch it, the script broke. If the SQL table got overwritten accidentally, there was no audit trail. The system worked — but only because one person held it together manually. That is not a sustainable architecture for a portfolio of this size or importance.

`[ADVANCE]`

---

## SLIDE 3 — THE SOLUTION

**Slide content:**
- Heading: "The Solution: A Single Source of Truth"
- Visual: Full **Before/After diagram** — showing the "After" = Django logo + caption "One place for all of the following"
- Key callout bullets:
  - Vendors log in and upload their own data — no spreadsheets, no email
  - Automated data integrity enforcement at the submission layer
  - A reviewer consolidates, validates, and publishes to a permanent master ledger
  - Embedded analytics serve live insights directly — no external BI tool required

**Script (~75 seconds):**

> The solution is the Rental Data Pipeline — a Django web application that replaces every step of that manual chain with a single, purpose-built platform. Instead of emailing a spreadsheet, vendors log into a secure portal and submit their weekly or monthly equipment data directly. Instead of running a C# upload script and manually copying, pasting data, a reviewer accesses a consolidated view of all vendor submissions, validates the data, and publishes it to a master ledger with a single action. Instead of building a separate Power BI report, analytics are embedded directly into the application.

> This is the essence of what we mean by a Single Source of Truth. The data goes in once, it's validated once, and every downstream view — including the analytics dashboard — reads from the same authoritative table. There's no spreadsheet to lose, no email thread to reconstruct, and no manual step that depends on a specific person being available. The system enforces the process.

`[ADVANCE]`

---

## SLIDE 4 — THE FOUR PILLARS

**Slide content:**
- Heading: "Synthesis: The Four Pillars"
- Table (replicate from README):

| Pillar | Metaphor | Role in This Project |
|---|---|---|
| Software Systems (SS) | The Muscle | Django MVT, role-based views, vendor portal, management commands, SDLC documentation |
| Business Analytics (BA) | The Brain | Plotly analytics dashboard — Cost Over Time, Compliance, Rent vs. Buy, Week Comparison |
| Data Management (DM) | The Skeleton | Normalized schema, staging → master publish workflow, audit table, ORM migrations |
| Cybersecurity & Networking (CN) | The Nervous System | Login required on all views, middleware-enforced routing, OTP 2FA, CSRF protection |

**Script (~90 seconds):**

> Before I walk through the application itself, I want to name the framework that makes this more than just a software project. The MS-CISBA curriculum is organized around four pillars — Software Systems, Business Analytics, Data Management, and Cybersecurity and Networking. The synthesis paper I wrote argues that these four pillars are not independent specializations. They are organs in a single organism, and every one of them is present in this application.

> Software Systems is the muscle — the Django framework, the role-based views, the vendor portal logic, the management commands that automate database operations. The muscle does the work.

> Business Analytics is the brain — the Plotly dashboard embedded in the application, showing spend trends, vendor compliance, and rent-versus-buy recommendations. The brain interprets the muscle's output into a decision.

> Data Management is the skeleton — the normalized database schema, the staging table that quarantines unverified data, the master ledger that only receives verified records, and the migration files that document how the schema evolved. The skeleton holds everything together.

> And Cybersecurity and Networking is the nervous system — the middleware that intercepts every request and routes it by role before any view logic runs, the two-factor authentication, the login-required decorators. The nervous system makes sure only the right signals reach the right organs.

`[ADVANCE]`

---

## SLIDE 5 — HOW THE PILLARS CONNECT

**Slide content:**
- Heading: "How It Works: The Weekly Data Cycle"
- Four-step numbered flow (can be a simple diagram or bold list):

  **Step 1 — Ingestion** (SS + CN): Vendor authenticates; middleware validates role before any data is touched

  **Step 2 — Storage** (DM + SS): Vendor submits data; form-validated rows written to `rental_staging` quarantine table

  **Step 3 — Review & Publish** (SS + DM + CN): Reviewer publishes verified staging rows to `rental_master`; `rvb_candidate` flag calculated at this moment

  **Step 4 — Interpretation** (BA): `rental_master` queried by analytics views; Plotly charts rendered for authorized users

- Footer note: "This cycle repeats every week. The organism breathes."

**Script (~75 seconds):**

> The four pillars don't just coexist in the application — they connect in a specific, ordered process that repeats every week. I call it the weekly data cycle.

> Step one is Ingestion. A vendor authenticates through the login portal. Before the view even loads, the middleware — that's our Networking and Security layer — validates the user's role and routes them to the correct part of the application. Only vendor-role users can reach their own specific vendor portal and only company personnel can see what all of that data looks like in a consolidated format..

> Step two is Storage. The vendor submits their equipment data. The Software layer validates every field — equipment ID, monthly rate, PO number — and writes the row to the `rental_staging` table. That table is a quarantine zone. Data lives there until a human reviewer approves it. Nothing in staging is considered "official."

> Step three is Review and Publish. The Junior Super User logs in, reviews the consolidated staging view across all vendors, and triggers the Publish to Master action. This bulk-transfers verified rows to the `rental_master` table, the Single Source of Truth. At this exact moment, the system also calculates which equipment items exceed market rate thresholds — flagging them as rent-versus-buy candidates.

> Step four is Interpretation. The analytics dashboard reads from `rental_master` and renders live charts showing spend trends, vendor compliance, and actionable fleet insights. The brain converts the skeleton's memory into a decision.

`[ADVANCE]`

---

## SLIDE 6 — DEMO: SECURE LOGIN & 2FA

**Slide content:**
- Heading: "Demo: Secure Login & Two-Factor Authentication"
- **Left image:** `Login Page.png` — Summit Vendor Portal login screen
- **Right image:** `2FA Prompt.png` — OTP verification code prompt
- Key callout: "All accounts — vendors, reviewers, and admin — require 2FA to enter. No SMTP in demo: code is always 111111."

**Script (~60 seconds):**

> Let's walk through the application. This is the login portal — the Summit Vendor Portal. Every user, regardless of role, enters through this screen. After submitting their username and password, they're immediately directed to a two-factor authentication prompt — you can see that on the right. They're asked to enter a six-digit code.

> In a production deployment, that code would be emailed to the user's verified address. In this demo environment, there's no SMTP server configured, so the code is hardcoded to 111111 for all accounts. But the mechanism itself is real — the `LoginOTP` model generates a code on every login attempt, and it is verified before granting session access. The security pattern is fully in place; only the email delivery is mocked for the demo.

> After successful verification, the middleware takes over and routes each user to their designated starting view — vendors go to the vendor portal, reviewers go to the weekly review page, and administrators go to the Django admin panel.

`[ADVANCE]`

---

## SLIDE 7 — DEMO: VENDOR PORTAL

**Slide content:**
- Heading: "Demo: Vendor Portal"
- **Image 1:** `Vendor Data.png` — Smith LLC vendor portal, Week 18 2026, 160 records, "Pending Submission" badge, Submit Weekly Report button
- **Image 2:** `Weekly Checkin Y-N to changes.png` — the cycle check-in modal ("Week 18 Check-In — Have any changes to your rental equipment occurred since last week? / Yes — I have changes / No — No changes")
- **Image 3:** `Confirm.png` — the submission confirmation dialog ("Submit Weekly Report — Week 18 / You are about to submit 160 equipment records for Smith LLC for Week 18, 2026 / Confirm & Submit")
- **Image 4:** `Success Ribbon.png` — post-submission state: green banner "Week 2026-04-27 rental data submitted successfully." + SUBMISSION STATUS badge changed to "Verified" + DECLARED AT timestamp
- Key callouts:
  - Vendor sees only their own data — no cross-vendor visibility
  - Inline editing: each row has edit/delete actions
  - CSV upload available for bulk changes
  - "Submit Weekly Report" locks the cycle and records the timestamp in `VendorAudit`

**Script (~75 seconds):**

> Once a vendor logs in, this is what they see — their own equipment portal. This screenshot shows Smith LLC's view for Week 18, 2026. They have 160 equipment records on file — pickup trucks, stake beds, and other fleet assets — each with a monthly rate, PO number, and RITM service request number. These fields map directly to the financial and procurement data the organization depends on.

> The system first shows a quick check-in modal asking whether any changes to their equipment have occurred since last week. If yes, they can update their rows before continuing; if no, they proceed directly to confirmation. Vendors can edit individual rows inline or bulk-upload changes via CSV. When they're ready to submit, they click "Submit Weekly Report." The confirmation dialog clearly states what is about to be submitted — vendor name, record count, and week number — before a final "Confirm & Submit" click locks it in. On submission, a green success banner confirms the action, the submission status badge changes from "Pending Submission" to "Verified," and a declared timestamp is recorded in the VendorAudit table.

> Notice what vendors cannot do: they cannot see any other vendor's data, cannot access the review page, and cannot publish anything to master. Every permission boundary is enforced at the middleware layer before the view even executes.

`[ADVANCE]`

---

## SLIDE 8 — DEMO: REVIEWER PORTAL

**Slide content:**
- Heading: "Demo: Reviewer Portal — Weekly Review & Publish"
- **Image 1:** `Review Before Data Uploaded.png` — "CONSOLIDATED EQUIPMENT — ALL VENDORS", 1474 records, Download CSV + Publish to Master buttons; full vendor data table sorted by rental company
- **Image 2:** `Confirm.png` (JSU/Review) — "Publish Week 18 to Master?" modal: "This will move all 1474 submitted records for Week 18, 2026 into the Master ledger. This action cannot be undone. / Cancel / Confirm & Publish"
- **Image 3:** `Ribbon.png` — post-publish state: green banner "Week 18, 2026 published — 1060 records moved to Master." + KPI summary cards: Total Vendors 25 · Submitted 24 · Pending 0 · Late 0 · Not Required 1
- Key callouts:
  - Reviewer sees all vendors consolidated into one table
  - Download CSV available for offline audit
  - Publish is irreversible — confirmation modal enforces intent
  - After publish, verified rows promote from `rental_staging` to `rental_master`; KPI dashboard confirms final headcount

**Script (~75 seconds):**

> This is the reviewer's view — the Weekly Review page, accessible only to the Junior Super User role. Instead of a single vendor's data, the reviewer sees all vendors consolidated into one table. In this screenshot, that's 1,474 records across all 25-plus vendors for Week 18, 2026. The reviewer can scroll through, look for anything that seems off, address suspicious rows, and download the full dataset as a CSV for offline audit if needed.

> When the reviewer is satisfied, they click "Publish to Master." A confirmation modal appears — clearly stating that 1,474 submitted records for Week 18 will be moved into the Master ledger and that this action cannot be undone. That's not just UX copy — the data model enforces it. Once a row is in `rental_master`.  It i intended to be the permanent record of what happened in that cycle; the only workaround being to access the company database itself in SQL. After publish, the page refreshes to a summary state: a green banner confirms how many records moved to master, and KPI cards show the final headcount — in this case 24 of 25 vendors submitted, zero pending, zero late, and one vendor classified as "Not Required" on a monthly cadence.

> This publish action is the most critical single moment in the weekly process. It's where Data Management meets Software Systems — the application executes a bulk database write that promotes verified staging data into the Single Source of Truth, and simultaneously flags any equipment items that exceed market rate thresholds for rent-versus-buy analysis.

`[ADVANCE]`

---

## SLIDE 9 — DEMO: ANALYTICS — SPEND OVER TIME

**Slide content:**
- Heading: "Demo: Analytics Dashboard — Spend & Utilization"
- **Main image:** `Cost Over Time.png` — Analytics Dashboard, Week 18 2026, 635 equipment, $462.80K/week, $1.85M/month, weekly cost trend chart
- Key callouts:
  - Live summary KPIs: equipment count, weekly spend, monthly run rate
  - Chart shows Week 1–18 of 2026 — spend trend visible across the year
  - Filters by vendor, department, rental category, PO number
  - "Export Report (PDF)" button for management reporting

**Script (~75 seconds):**

> After publish, the data is immediately visible in the analytics dashboard — accessible only to the reviewer role. This is where Business Analytics becomes the centerpiece. The top row shows the live KPIs for the most recent published week: 635 pieces of equipment on rent, $462,800 in weekly rental spend, and a $1.85 million monthly run rate. These numbers update every time a new week is published — no manual refresh, no spreadsheet to re-pull.

> The chart below it shows weekly rental cost across every cycle published so far in 2026 — Weeks 1 through 18 in this screenshot. You can see the steady climb as the fleet grew through the first half of the year. The dashboard is filterable by department, by supplier, by rental category, and by PO number — so a manager can drill into exactly the portion of the fleet relevant to their budget.

> There's also an Export Report to PDF button in the upper right. In a fully realized system, this button would generate a management-ready report for distribution without ever touching a BI tool.

`[ADVANCE]`

---

## SLIDE 10 — DEMO: ANALYTICS — WEEKLY COMP & RAW LEDGER

**Slide content:**
- Heading: "Demo: Analytics – Weekly Comp & Raw Ledger"
- **Left image:** `Week Comp.png` — week-over-week comparison view showing equipment taken on/off rent between cycles
- **Right image:** `Raw Ledger.png` — full paginated table of every record in the master database
- Key callouts:
  - Weekly Comp: instant delta view — what was added and removed from the fleet week to week
  - Raw Ledger: complete, filterable audit table of every master record — no aggregation, just the data

**Script (~60 seconds):**

> Two additional views round out the analytics dashboard. The first is the Weekly Comparison chart — a week-over-week delta view showing plainly what equipment was taken on rent and what came off rent between cycles. For a fleet manager, this answers "what changed this week?" without manually comparing two spreadsheets.

> The second is the Raw Ledger — a direct, paginated table of every record currently in the master database. No aggregation, no chart — just the underlying data, fully visible and filterable. This view exists because sometimes the right analytical tool is simply being able to see the raw numbers. Together, these two views give the reviewer both the story of change and the source of truth in one place.

`[ADVANCE]`

---

## SLIDE 11 — DEMO: ANALYTICS — COMPLIANCE & RENT V. BUY

**Slide content:**
- Heading: "Demo: Analytics – Compliance & Rent v. Buy"
- **Left image:** `Compliance.png` — Vendor Submission Compliance bar chart (all green = verified, all 25 vendors)
- **Right image:** `Rent v Buy.png` — Rent vs. Buy Candidates table (Caterpillar loaders flagged "Consider Purchasing," with monthly rate, months on rent, estimated buy price, breakeven)
- Key callouts:
  - Compliance chart: instant visibility into which vendors have submitted, which are late, which are pending
  - Rent-vs-Buy: automatically calculated when a record crosses the monthly rate threshold relative to purchase price + maintenance
  - "Consider Purchasing" flag surfaces directly from data — no analyst intervention required

**Script (~75 seconds):**

> Two more analytical views worth highlighting. On the left is the Vendor Submission Compliance chart. Every bar represents a vendor — and when they're all green, as they are here, it means every vendor has submitted and been verified for the current cycle. In a real deployment, late and pending bars would show in orange and red, giving the reviewer an instant snapshot of who hasn't checked in without having to dig through a spreadsheet or call anyone.

> On the right is the Rent vs. Buy Candidates table — and this is where I think the analytical value of the system really comes through. Every time a week is published, the application compares each equipment item's monthly rental rate against the estimated purchase price and ongoing maintenance cost stored in the EquipmentMarketRate reference table. Any item where it would be cheaper to own than to rent is flagged and surfaces here automatically. You can see Caterpillar loaders from West Inc. — some at $24,000 per month — flagged as "Consider Purchasing," with a calculated breakeven of roughly 17 to 22 months. That is a strategic capital decision surfacing automatically from operational data. No analyst has to run a separate model.

`[ADVANCE]`

---

## SLIDE 12 — THE FULLY REALIZED VISION

**Slide content:**
- Heading: "The Fully Realized Vision"
- Subheading: "What this system would look like in production"
- Bullet list (two columns):

  **Infrastructure & Security**
  - PostgreSQL replacing SQLite (concurrent users, row-level locking)
  - HTTPS / TLS enforced at the load balancer level
  - Live OTP email delivery via SendGrid or AWS SES (no hardcoded codes)
  - Audit log table capturing every publish, edit, and delete action with user + timestamp

  **Analytical Capabilities**
  - Multi-year trend analysis as the master ledger grows
  - Budget variance tracking: actual spend vs. departmental allocation
  - Automated late-submission alerts and vendor scorecards
  - AI-assisted anomaly detection on rate outliers (sudden spikes in monthly rate for the same asset)

  **Operational Workflow**
  - Automated weekly cycle advance — no manual management commands needed
  - Email reminders to vendors approaching their submission deadline
  - Role expansion: department budget approvers with limited-scope analytics access
  - CSV import from vendor ERP systems (reducing manual entry entirely)

**Script (~90 seconds):**

> What you've seen so far is a working prototype — it runs locally, it processes real data, and it demonstrates every key workflow from login to publish to analytics. But it's worth being honest about what "fully realized" would look like if this were deployed at scale.

> On the infrastructure and security side, the first change would be swapping SQLite for PostgreSQL. SQLite is fine for a single-user demo, but a system with 25 simultaneous vendor submissions needs true concurrent write handling. TLS would be enforced at the load balancer — no unencrypted traffic. And the OTP authentication, which is already architecturally complete, would connect to a real email delivery service. The code is already there; it's just a configuration change.

> On the analytical side, the dashboard would become significantly more powerful as the master ledger accumulates multi-year data. Trend analysis across 2024, 2025, and 2026 would give leadership the ability to see long-term fleet cost patterns, not just the current year. Automated budget variance tracking — comparing actual rental spend to departmental allocations — would replace the manual reconciliation process that currently happens in Excel. And a machine learning layer watching for rate anomalies — a vendor suddenly billing $5,000 per month for an asset that was $800 per month the year before — would surface data quality issues before they reach the master ledger.

> On the operational workflow side, the weekly cycle advance that currently requires a management command would be automated entirely. Vendors would receive email reminders as their submission deadline approached, and the review page would automatically reflect which vendors were on time, which were late, and which hadn't been heard from.

`[ADVANCE]`

---

## SLIDE 13 — SYNTHESIS REFLECTION

**Slide content:**
- Heading: "Why This Is a Synthesis — Not Just a Software Project"
- Visual: The four-pillar table again (from Slide 4), but each row now has a "What breaks without it?" column:

| Pillar | What breaks if removed? |
|---|---|
| **Software Systems** | There is no application. No portal, no forms, no publish action. The entire pipeline disappears. |
| **Business Analytics** | The data is collected and stored, but no one can interpret it. Decisions revert to gut feel and spreadsheets. |
| **Data Management** | There's no schema to enforce integrity. Vendors submit garbage. The "master ledger" is meaningless. |
| **Cybersecurity & Networking** | Any user can reach any view. Vendors see competitors' data. The dataset is compromised before it starts. |

- Footer callout: *"A system where removing any single pillar causes total failure is, by definition, a synthesis."*

**Script (~90 seconds):**

> I want to close the technical portion with the argument that I believe is the core of this project's academic purpose. What makes this a synthesis demonstration — not just a software project that happens to have analytics in it — is that you cannot remove any one of the four pillars and still have a functioning system.

> Remove Software Systems, and there is no application. There's no portal, no form submission, no publish button, no dashboard. The problem reverts entirely to email and Excel.

> Remove Business Analytics, and the data gets collected and stored — but no one can interpret it. Leadership goes back to gut feel. The Rent vs. Buy analysis never happens. Equipment runs past its cost-optimal point indefinitely.

> Remove Data Management, and there's no schema enforcing what "clean data" means. Vendors submit whatever they want. The staging-to-master pipeline doesn't exist. The analytics dashboard reads from a corrupted table and produces meaningless numbers.

> Remove Cybersecurity and Networking, and the middleware disappears. A vendor can navigate directly to the review page. A reviewer can see a competitor's rates. An anonymous user can publish to master. The entire trust model of the system collapses before a single piece of data is entered.

> A system where removing any single pillar causes total failure is, by definition, a synthesis. That is what this project demonstrates.

`[ADVANCE]`

---

## SLIDE 14 — CONCLUSION

**Slide content:**
- Heading: "Thank You"
- Clean slide with:
  - Project name: Rental Data Pipeline
  - Author: Alexander J. Lawson
  - Course: CIDM-6395 Capstone | West Texas A&M University | April 2026
  - Optional: Hosted demo URL — `https://cidm-6395-alexander-lawson.onrender.com/login/`
  - Optional: GitHub/repo reference if applicable

**Script (~45 seconds):**

> To summarize: the Rental Data Pipeline is a working demonstration that a $2–$3 million equipment rental process that was previously managed by one person, a spreadsheet, and a prayer can be replaced by a structured, audited, multi-role web application that enforces data integrity, automates compliance tracking, and surfaces actionable financial intelligence in real time. It required all four pillars of the MS-CISBA curriculum to build — and it requires all four to function. That is the synthesis. Thank you.

---

---

## SPEAKER REFERENCE: TIMING GUIDE

| Slide | Title | Est. Time |
|---|---|---|
| 1 | Title | 0:30 |
| 2 | The Problem | 1:15 |
| 3 | The Solution | 1:15 |
| 4 | The Four Pillars | 1:30 |
| 5 | How the Pillars Connect | 1:15 |
| 6 | Secure Login & 2FA | 1:00 |
| 7 | Vendor Portal | 1:15 |
| 8 | Reviewer Portal | 1:15 |
| 9 | Analytics — Spend Over Time | 1:15 |
| 10 | Analytics — Weekly Comp & Raw Ledger | 1:00 |
| 11 | Analytics — Compliance & Rent v. Buy | 1:15 |
| 12 | Fully Realized Vision | 1:30 |
| 13 | Synthesis Reflection | 1:30 |
| 14 | Conclusion | 0:45 |
| | **Total** | **~16:30 at a measured pace / ~13 min at a normal pace** |

> **Tip:** Slides 4, 5, 12, and 13 are the "argument" slides — slow down on those. Slides 6–11 are the demo — you can move through them more quickly if you're also clicking through a live app or screen recording.

---

## IMAGE PLACEMENT REFERENCE

| Slide | Image File | Subfolder |
|---|---|---|
| 2 | Before v After.png (top half) | `/deliverables/Capstone PowerPoint Images/` |
| 3 | Before v After.png (full) | `/deliverables/Capstone PowerPoint Images/` |
| 6 | Login Page.png | `/deliverables/Capstone PowerPoint Images/` |
| 6 | 2FA Prompt.png | `/deliverables/Capstone PowerPoint Images/` |
| 7 | Vendor Data.png | `/deliverables/Capstone PowerPoint Images/Vendor/` |
| 7 | Weekly Checkin Y-N to changes.png | `/deliverables/Capstone PowerPoint Images/Vendor/` |
| 7 | Confirm.png | `/deliverables/Capstone PowerPoint Images/Vendor/` |
| 7 | Success Ribbon.png | `/deliverables/Capstone PowerPoint Images/Vendor/` |
| 8 | Review Before Data Uploaded.png | `/deliverables/Capstone PowerPoint Images/JSU/Review/` |
| 8 | Confirm.png | `/deliverables/Capstone PowerPoint Images/JSU/Review/` |
| 8 | Ribbon.png | `/deliverables/Capstone PowerPoint Images/JSU/Review/` |
| 9 | Cost Over Time.png | `/deliverables/Capstone PowerPoint Images/JSU/Analytics/` |
| 10 | Week Comp.png | `/deliverables/Capstone PowerPoint Images/JSU/Analytics/` |
| 10 | Raw Ledger.png | `/deliverables/Capstone PowerPoint Images/JSU/Analytics/` |
| 11 | Compliance.png | `/deliverables/Capstone PowerPoint Images/JSU/Analytics/` |
| 11 | Rent v Buy.png | `/deliverables/Capstone PowerPoint Images/JSU/Analytics/` |
