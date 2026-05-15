# User Login Reference

**Project:** Equipment Rental Data Pipeline
**Environment:** Local Development
**Last Updated:** 2026-05-19
**Owner:** Alexander J. Lawson

> ⚠️ **Development Use Only.**
> This document contains seed credentials for the local SQLite development environment.
> Do not commit real passwords to source control. Do not reuse these credentials in any production or shared environment.

> 🔐 **2FA Note:** All accounts require a 6-digit OTP after login. No SMTP server is configured — no email is sent. The code is hardcoded to **`111111`** for all demo accounts.

---

## Administrator

| Username | Password | Role | Portal Access |
| :--- | :--- | :--- | :--- |
| `admin` | `<redacted>` | Administrator | Django Admin — full access |

- Full CRUD on all models, users, and groups.
- Can publish staging rows to master.
- Can access `/analytics/` dashboard.

---

## Junior Super Users (Operations Approvers)

| Username | Initial Password | Role | Portal Access |
| :--- | :--- | :--- | :--- |
| `junior_super_01` | `<redacted>` | Junior Super User | Django Admin — all vendors |


- Can view and edit staging and master records for all 25 vendors.
- Can publish validated staging rows to master.
- Intended to receive CC on automated deadline nudge emails — **not active in this demo** (no SMTP configured).
- Can access `/analytics/` dashboard.
- Cannot manage users or system settings.

---

## Vendor Users (1 per Company)

| Username | Initial Password | Company |
| :--- | :--- | :--- |
| `vendor_atkins_taylor_and_hughes` | `<redacted>` | Atkins, Taylor and Hughes |
| `vendor_brown_group` | `<redacted>` | Brown Group |
| `vendor_christensen_nixon_and_davis` | `<redacted>` | Christensen, Nixon and Davis |
| `vendor_chung_cannon` | `<redacted>` | Chung-Cannon |
| `vendor_davidson_plc` | `<redacted>` | Davidson PLC |
| `vendor_griffin_ltd` | `<redacted>` | Griffin Ltd |
| `vendor_harris_llc` | `<redacted>` | Harris LLC |
| `vendor_kelley_acosta_and_salazar` | `<redacted>` | Kelley, Acosta and Salazar |
| `vendor_lee_jordan` | `<redacted>` | Lee-Jordan |
| `vendor_marshall_group` | `<redacted>` | Marshall Group |
| `vendor_mclaughlin_banks_and_grant` | `<redacted>` | Mclaughlin, Banks and Grant |
| `vendor_morales_allen_and_jones` | `<redacted>` | Morales, Allen and Jones |
| `vendor_myers_inc` | `<redacted>` | Myers Inc |
| `vendor_nguyen_and_sons` | `<redacted>` | Nguyen and Sons |
| `vendor_nguyen_ltd` | `<redacted>` | Nguyen Ltd |
| `vendor_nunez_group` | `<redacted>` | Nunez Group |
| `vendor_peterson_kelly_and_arnold` | `<redacted>` | Peterson, Kelly and Arnold |
| `vendor_preston_llc` | `<redacted>` | Preston LLC |
| `vendor_reyes_and_sons` | `<redacted>` | Reyes and Sons |
| `vendor_robbins_and_sons` | `<redacted>` | Robbins and Sons |
| `vendor_smith_llc` | `<redacted>` | Smith LLC |
| `vendor_taylor_figueroa_and_brown` | `<redacted>` | Taylor, Figueroa and Brown |
| `vendor_trevino_inc` | `<redacted>` | Trevino Inc |
| `vendor_west_inc` | `<redacted>` | West Inc |
| `vendor_wilson_chen_and_morrison` | `<redacted>` | Wilson, Chen and Morrison |

**Vendor role restrictions:**
- Can view and edit staging records for their own company only.
- Can submit a "No Changes this week" declaration via the `vendor_audit` admin action.
- Cannot access `/analytics/` dashboard (returns HTTP 403).
- Cannot publish to master or manage users.

---

## Role Summary

| Role | Django Admin | Analytics Tab | Publish to Master | Cross-Vendor View |
| :--- | :---: | :---: | :---: | :---: |
| Administrator | ✅ Full | ✅ | ✅ | ✅ |
| Junior Super User | ✅ Scoped | ✅ | ✅ | ✅ |
| Vendor | ✅ Own data only | ❌ | ❌ | ❌ |

---

## Re-Seeding Credentials

If you need to regenerate vendor or junior super user passwords, re-run the seed command with the reset flag:

```bash
python manage.py seed_user_schema --csv ../docs/Rental_Report_DUMMY.csv
```

New passwords are randomly generated and stored in `UserProfile.initial_password`.
They are visible in the Django Admin under **User Profiles** for reference during development.
