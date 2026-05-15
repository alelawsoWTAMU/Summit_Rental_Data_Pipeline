# AI Usage Disclosure

**Project:** Equipment Rental Data Pipeline (CIDM-6395 Capstone)
**Owner:** Alexander J. Lawson
**Last Updated:** 2026-04-22

---

## Overview

This document discloses the use of AI-assisted tools throughout the development of the Equipment Rental Data Pipeline capstone project. All AI assistance is acknowledged here in accordance with academic integrity standards for CIDM-6395.

---

## Tools Used

| Tool | Version / Model | Provider |
| :--- | :--- | :--- |
| GitHub Copilot (Chat & Inline) | Claude Sonnet 4.6 | Microsoft / Anthropic |

---

## Scope of AI Assistance

### 1. Session Documentation (ADR / PRD / Brief)
AI was used to draft and format all Architecture Requirements Documents (ADR), Product Requirements Documents (PRD), and Session Briefs for each development session (2026412, 2026419, 2026420, 2026422). The student provided all source material — session outcomes, design decisions, implementation details, and business context — which the AI organized into the established document templates. All factual content reflects actual work performed by the student; the AI served as a structured writing assistant.

### 2. Code Scaffolding and Boilerplate
GitHub Copilot inline suggestions were used to accelerate the generation of repetitive boilerplate, including:
- Django model field definitions and migration scaffolding.
- Management command `handle()` method structure and argument parser setup.
- HTML table and form markup in `vendor_dashboard.html`, `weekly_review.html`, and `analytics.html`.
- Django admin `ModelAdmin` class configuration (list_display, list_filter, search_fields).

All scaffolded code was reviewed, tested, and modified by the student before integration.

### 3. Debugging and Diagnostic Assistance
AI chat was used to diagnose and resolve several specific technical issues:
- **ISO Week Year Bucketing Bug:** AI helped identify the root cause — ISO week year (`record.year`) diverging from calendar year in late December — and proposed the fix using `isoWeekStartDate(record.year, record.week).getUTCFullYear()`.
- **Plotly Tab Performance:** AI identified that dispatching a global `window.resize` event forced all hidden charts to relayout simultaneously and suggested targeted `Plotly.Plots.resize(el)` as the fix.
- **Django ORM Query Construction:** AI assisted with constructing multi-table join queries (e.g., `RentalMaster` → `PODepartment` → `EquipmentMarketRate`) and annotating querysets for use in chart views.
- **`check_deadlines` SMTP Logic:** AI assisted with structuring the deadline detection loop and email dispatch using Django's `send_mail` with environment variable credential sourcing.

### 4. Seed Data Generation
AI was used to generate plausible fictional data for:
- Vendor company names (all placeholder identities — no real company names).
- Equipment descriptions mapped to `EquipmentMarketRate` reference entries.
- W16 and W17 scenario row construction in `simulate_vendor_week`.

The student defined all data rules, quantities, and business constraints. AI produced data conforming to those rules.

### 5. UX Copy and Template Text
Minor UI copy — including stat card labels, badge text, empty-state messages, and the auto-summary paragraph template on the Cost Over Time tab — was drafted with AI assistance and reviewed by the student.

---

## What AI Did Not Do

- AI did not define the project's business requirements, architecture, or data model. All structural decisions (staging/master/audit schema, role hierarchy, RvB threshold logic, mill department taxonomy) originated with the student based on real-world domain knowledge from their professional context.
- AI did not perform testing or verify that the application functions as described. All scenario validation (S-01 through S-08), UI verification, and publish workflow testing was conducted by the student.
- AI did not write the Assignment submissions (Assignments 1–4). Those documents reflect the student's own analysis and self-assessment.
- AI did not have access to any proprietary employer data. All vendor names, PO numbers, and rental figures in the project are fictional or anonymized.

---

## Human Review Process

Every AI-generated output — code, documentation, or data — was reviewed by the student before use. Code was tested locally against the SQLite development database. Documentation was compared against actual session work and corrected where AI inferred details incorrectly. No AI output was accepted without review.

---

## Academic Integrity Statement

The use of AI tools in this project is consistent with the guidelines communicated for CIDM-6395. AI was used as a productivity tool to assist with writing, scaffolding, and debugging — not as a substitute for the student's own understanding, judgment, or decision-making. The student accepts full responsibility for all content, code, and design choices in this project.
