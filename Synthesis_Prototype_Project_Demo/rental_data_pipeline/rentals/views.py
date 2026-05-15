import datetime
import logging
import secrets

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.views.decorators.http import require_POST
import json
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

logger = logging.getLogger(__name__)

from .models import ApprovedEquipmentCategory, EquipmentMarketRate, LoginOTP, PODepartment, RentalMaster, RentalStaging, SubmissionStatus, VendorAudit, VendorCompany


def _get_profile(user):
    return getattr(user, "profile", None)


def _is_vendor(user):
    profile = _get_profile(user)
    return bool(profile and profile.role == "vendor")


def _default_home_for_user(user):
    profile = _get_profile(user)
    if not profile:
        return "/login/"
    if profile.role == "admin":
        return "/admin/"
    if profile.role == "junior_superuser":
        return "/review/"
    if profile.role == "vendor":
        return "/vendor/"
    return "/login/"


def portal_login(request):
    """Portal login — step 1: validate credentials, issue OTP, redirect to verify."""
    if request.user.is_authenticated:
        return redirect(_default_home_for_user(request.user))

    next_url = request.POST.get("next") or request.GET.get("next") or ""
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        # Issue a fixed demo OTP (always "111111") and redirect to the verify step.
        DEMO_OTP_CODE = "111111"
        LoginOTP.objects.filter(user=user, is_used=False).update(is_used=True)
        otp = LoginOTP.objects.create(user=user, code=DEMO_OTP_CODE)
        request.session["_2fa_pending_user_id"] = user.pk
        if next_url:
            request.session["_2fa_next"] = next_url
        # Attempt to send the code by email; log failures but do not block login.
        try:
            send_mail(
                subject="Your Vendor Portal verification code",
                message=(
                    f"Your one-time sign-in code is: {DEMO_OTP_CODE}\n\n"
                    "This code expires in 10 minutes.\n"
                    "If you did not request this, please ignore this email."
                ),
                from_email=None,
                recipient_list=[user.email] if user.email else [],
                fail_silently=False,
            )
        except Exception as exc:
            logger.warning("OTP email failed for user %s: %s", user.username, exc)
        return redirect("verify_otp")

    return render(
        request,
        "admin/login.html",
        {
            "form": form,
            "next": next_url,
            "app_path": request.path,
        },
    )


def verify_otp(request):
    """Portal login — step 2: validate the 6-digit OTP emailed to the user."""
    pending_user_id = request.session.get("_2fa_pending_user_id")
    if not pending_user_id:
        return redirect("portal_login")

    error = None

    if request.method == "POST":
        submitted_code = request.POST.get("code", "").strip()
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=pending_user_id)
        except Exception:
            del request.session["_2fa_pending_user_id"]
            return redirect("portal_login")

        otp = (
            LoginOTP.objects
            .filter(user=user, is_used=False)
            .order_by("-created_at")
            .first()
        )
        if otp and otp.is_valid() and otp.code == submitted_code:
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            next_url = request.session.pop("_2fa_next", "")
            del request.session["_2fa_pending_user_id"]
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect(_default_home_for_user(user))
        else:
            error = "Invalid or expired code. Please try again or go back to request a new code."

    return render(request, "rentals/verify_otp.html", {"error": error})


@login_required
@require_POST
def portal_logout(request):
    """Log out and return to the portal login page."""
    logout(request)
    return redirect("/login/")


@login_required
def analytics_export_report(request):
    user = request.user
    profile = _get_profile(user)

    if _is_vendor(user) or not profile or profile.role != "junior_superuser":
        return HttpResponseForbidden(
            "Access denied. The analytics export is restricted to reviewer operations staff."
        )

    master_qs = RentalMaster.objects.filter(is_active=True)
    week_filter = (request.GET.get("week") or "").strip()
    area_filter = (request.GET.get("area") or "").strip()
    vendor_filter = (request.GET.get("vendor") or "").strip()
    category_filter = (request.GET.get("category") or "").strip()
    po_filter = (request.GET.get("po") or "").strip()

    if week_filter:
        try:
            y, w = week_filter.split("-", 1)
            master_qs = master_qs.filter(cycle_year=int(y), cycle_week=int(w))
        except ValueError:
            pass
    if area_filter:
        dept_pos = PODepartment.objects.filter(
            department__icontains=area_filter
        ).values_list("po_number", flat=True)
        master_qs = master_qs.filter(po_number__in=dept_pos)
    if vendor_filter:
        master_qs = master_qs.filter(vendor_name__icontains=vendor_filter)
    if category_filter:
        master_qs = master_qs.filter(equipment_category__icontains=category_filter)
    if po_filter:
        master_qs = master_qs.filter(po_number__icontains=po_filter)

    daily_cost_expr = ExpressionWrapper(F("rate_daily") * F("quantity"), output_field=DecimalField())

    cycle_totals = list(
        master_qs
        .values("cycle_year", "cycle_week")
        .annotate(total=Sum(daily_cost_expr), total_qty=Sum("quantity"))
        .order_by("cycle_year", "cycle_week")
    )

    latest_cycle = cycle_totals[-1] if cycle_totals else None
    latest_label = (
        f"{latest_cycle['cycle_year']}-W{latest_cycle['cycle_week']:02d}"
        if latest_cycle and latest_cycle["cycle_year"] and latest_cycle["cycle_week"] else "N/A"
    )
    latest_qty = int((latest_cycle or {}).get("total_qty") or 0)
    latest_monthly = float((latest_cycle or {}).get("total") or 0)
    latest_weekly = latest_monthly * 0.25
    prior_monthly = float(cycle_totals[-2]["total"] or 0) if len(cycle_totals) >= 2 else 0.0
    weekly_delta = (latest_monthly - prior_monthly) * 0.25 if cycle_totals else 0.0
    weekly_delta_pct = ((latest_monthly - prior_monthly) / prior_monthly * 100.0) if prior_monthly else 0.0

    spend_top = list(
        master_qs.values("vendor_name")
        .annotate(total=Sum(daily_cost_expr))
        .order_by("-total")[:5]
    )
    total_monthly_all = sum(float(d["total"] or 0) for d in spend_top)
    top_supplier_share = (
        (float(spend_top[0]["total"] or 0) / total_monthly_all * 100.0)
        if spend_top and total_monthly_all else 0.0
    )
    category_top = list(
        master_qs.values("equipment_description")
        .annotate(total=Sum(daily_cost_expr))
        .order_by("-total")[:5]
    )

    available_cycles = [
        (d["cycle_year"], d["cycle_week"])
        for d in cycle_totals if d["cycle_year"] and d["cycle_week"]
    ]
    placed_count = 0
    removed_count = 0
    if len(available_cycles) >= 2:
        prev_year, prev_week = available_cycles[-2]
        curr_year, curr_week = available_cycles[-1]
        prev_rows = set(
            master_qs.filter(cycle_year=prev_year, cycle_week=prev_week)
            .values_list("vendor_name", "equipment_id")
        )
        curr_rows = set(
            master_qs.filter(cycle_year=curr_year, cycle_week=curr_week)
            .values_list("vendor_name", "equipment_id")
        )
        placed_count = len(curr_rows - prev_rows)
        removed_count = len(prev_rows - curr_rows)

    allowed_vendors = list(master_qs.values_list("vendor_name", flat=True).distinct())
    audit_qs = VendorAudit.objects.filter(vendor_name__in=allowed_vendors) if allowed_vendors else VendorAudit.objects.none()
    verified_count = audit_qs.filter(verified=True).count()
    late_count = audit_qs.filter(is_late=True).count()
    pending_count = max(0, audit_qs.count() - verified_count - late_count)

    market_lookup = {}
    for m in EquipmentMarketRate.objects.order_by("equipment_description", "-effective_date"):
        market_lookup.setdefault(m.equipment_description, float(m.rvb_monthly_threshold))

    rvb_candidates = []
    if latest_cycle:
        latest_rows = master_qs.filter(
            cycle_year=latest_cycle["cycle_year"], cycle_week=latest_cycle["cycle_week"]
        ).values("vendor_name", "equipment_id", "equipment_description", "rate_daily", "quantity")
        for row in latest_rows:
            threshold = market_lookup.get(row["equipment_description"])
            if threshold is None:
                continue
            monthly_rent = float(row["rate_daily"] or 0) * (row["quantity"] or 0)
            overage = monthly_rent - threshold
            if overage <= 0:
                continue
            rvb_candidates.append((overage, row))
        rvb_candidates.sort(key=lambda x: x[0], reverse=True)

    from io import BytesIO
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    def to_png(fig):
        buf = BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=140)
        plt.close(fig)
        buf.seek(0)
        return buf

    def chart_cost():
        labels = [f"{d['cycle_year']}-W{d['cycle_week']:02d}" for d in cycle_totals]
        vals = [float(d["total"] or 0) * 0.25 for d in cycle_totals]
        fig, ax = plt.subplots(figsize=(7.2, 2.7))
        ax.plot(labels, vals, marker="o", linewidth=2.2, color="#1d6fb8")
        ax.set_title("Cost Over Time (Weekly)")
        ax.set_ylabel("USD")
        ax.tick_params(axis="x", rotation=30, labelsize=7)
        ax.grid(alpha=.25)
        return to_png(fig)

    def chart_bar(data, label_key, value_key, title):
        labels = [str(d[label_key] or "Unknown") for d in data]
        vals = [float(d[value_key] or 0) for d in data]
        labels = labels[::-1]
        vals = vals[::-1]
        fig, ax = plt.subplots(figsize=(7.2, 2.6))
        ax.barh(labels, vals, color="#1d6fb8")
        ax.set_title(title)
        ax.set_xlabel("USD / month")
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="x", alpha=.2)
        return to_png(fig)

    def chart_comparison():
        fig, ax = plt.subplots(figsize=(7.2, 2.2))
        ax.bar(["Placed On-Rent", "Taken Off Rent"], [placed_count, removed_count], color=["#16a34a", "#dc2626"])
        ax.set_title("Week Comparison")
        ax.set_ylabel("Equipment Count")
        return to_png(fig)

    def chart_rvb():
        top = rvb_candidates[:8]
        labels = [f"{row['vendor_name']} {row['equipment_id']}" for _, row in top][::-1]
        vals = [float(overage) for overage, _ in top][::-1]
        fig, ax = plt.subplots(figsize=(7.2, 2.6))
        ax.barh(labels, vals, color="#b91c1c")
        ax.set_title("Top Rent-vs-Buy Savings Opportunities")
        ax.set_xlabel("Estimated savings if owned ($ / month)")
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(axis="x", alpha=.2)
        return to_png(fig)

    active_filter_text = (
        f"week={week_filter or 'all'}, area={area_filter or 'all'}, vendor={vendor_filter or 'all'}, "
        f"category={category_filter or 'all'}, po={po_filter or 'all'}"
    )

    trend_phrase = "stable"
    if weekly_delta > 0:
        trend_phrase = "upward"
    elif weekly_delta < 0:
        trend_phrase = "downward"

    synopsis_p1 = (
        f"The current snapshot covers {len(cycle_totals)} reporting points and shows a latest weekly spend of "
        f"${latest_weekly:,.2f} across {latest_qty:,} equipment units in cycle {latest_label}. "
        f"Compared with the immediately prior period, weekly spend moved by "
        f"{'+' if weekly_delta >= 0 else '-'}${abs(weekly_delta):,.2f} "
        f"({abs(weekly_delta_pct):.1f}% {'increase' if weekly_delta >= 0 else 'decrease'}), "
        f"suggesting a {trend_phrase} near-term cost trend."
    )

    synopsis_p2 = (
        f"Spend concentration remains a key monitoring point. The top supplier currently accounts for "
        f"approximately {top_supplier_share:.1f}% of tracked monthly spend in this filter scope. "
        f"Week comparison indicates {placed_count} additions and {removed_count} removals, while compliance signals "
        f"{verified_count} verified, {late_count} late, and {pending_count} pending submissions. "
        f"Rent-vs-buy analysis identified {len(rvb_candidates)} lines where ownership is currently estimated to be more cost-effective than continued renting."
    )

    brand_navy = colors.HexColor("#0b2a4a")
    brand_blue = colors.HexColor("#1d6fb8")
    brand_green = colors.HexColor("#2ea86b")
    light_panel = colors.HexColor("#eef3f9")
    slate_text = colors.HexColor("#334155")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodySmall", fontSize=9.5, leading=13, textColor=slate_text))
    styles.add(ParagraphStyle(name="SectionTitle", fontSize=12.5, leading=15, textColor=brand_navy, spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="ReportIntro", fontSize=9.2, leading=12.5, textColor=colors.HexColor("#1f2d3d")))
    styles.add(ParagraphStyle(name="MetaSmall", fontSize=8.4, leading=11.5, textColor=colors.HexColor("#e2e8f0")))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=34,
        leftMargin=34,
        topMargin=78,
        bottomMargin=28,
        title="Analytics Synopsis Report",
    )

    def draw_header_footer(canvas, document):
        page_w, page_h = letter
        canvas.saveState()
        canvas.setFillColor(brand_navy)
        canvas.rect(0, page_h - 58, page_w, 58, stroke=0, fill=1)
        canvas.setFillColor(brand_green)
        canvas.rect(0, page_h - 58, page_w, 2, stroke=0, fill=1)

        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(36, page_h - 30, "Rental Analytics Report")
        canvas.setFont("Helvetica", 8)
        canvas.drawString(36, page_h - 43, f"Generated {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}  |  User: {request.user.username}")

        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setLineWidth(0.6)
        canvas.line(34, 24, page_w - 34, 24)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(page_w - 34, 12, f"Page {document.page}")
        canvas.restoreState()

    def section_divider():
        bar = Table([[""], [""]], colWidths=[6.9 * inch], rowHeights=[1, 6])
        bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_green),
            ("BACKGROUND", (0, 1), (-1, 1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ]))
        return bar

    story = []
    intro_panel = Table(
        [[Paragraph(
            "This export provides a snapshot of current rental performance and highlights where spend and rent-vs-buy opportunities are concentrated. "
            f"Active filters: {active_filter_text}",
            styles["ReportIntro"],
        )]],
        colWidths=[6.9 * inch],
    )
    intro_panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), light_panel),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(intro_panel)
    story.append(Spacer(1, 0.16 * inch))

    story.append(Paragraph("Synopsis", styles["SectionTitle"]))
    story.append(Paragraph(synopsis_p1, styles["BodySmall"]))
    story.append(Spacer(1, 0.04 * inch))
    story.append(Paragraph(synopsis_p2, styles["BodySmall"]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(section_divider())
    story.append(Spacer(1, 0.06 * inch))

    kpi_table = Table([
        ["Latest Cycle", "Equipment Count", "Per Week", "Per Month"],
        [latest_label, f"{latest_qty:,}", f"${latest_weekly:,.2f}", f"${latest_monthly:,.2f}"],
    ], colWidths=[1.72 * inch, 1.72 * inch, 1.72 * inch, 1.72 * inch])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_navy),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("FONTSIZE", (0, 1), (-1, 1), 11),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, 1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.12 * inch))
    story.append(section_divider())

    story.append(Paragraph("Cost Over Time", styles["SectionTitle"]))
    story.append(Paragraph(
        f"Snapshot of weekly spend trajectory across {len(cycle_totals)} reporting points in the current filter scope.",
        styles["BodySmall"],
    ))
    if cycle_totals:
        story.append(Image(chart_cost(), width=6.9 * inch, height=2.55 * inch))
    else:
        story.append(Paragraph("No cost-over-time data is available for this filter set.", styles["BodySmall"]))

    story.append(Spacer(1, 0.08 * inch))
    story.append(section_divider())
    story.append(Paragraph("Top Supplier and Rental Category Spend", styles["SectionTitle"]))
    story.append(Paragraph(
        "These visuals identify concentration of spend by supplier and equipment category.",
        styles["BodySmall"],
    ))
    if spend_top:
        story.append(Image(chart_bar(spend_top, "vendor_name", "total", "Top Suppliers by Monthly Spend"), width=6.9 * inch, height=2.45 * inch))
    if category_top:
        story.append(Image(chart_bar(category_top, "equipment_description", "total", "Top Categories by Monthly Spend"), width=6.9 * inch, height=2.45 * inch))

    story.append(Spacer(1, 0.08 * inch))
    story.append(section_divider())
    story.append(Paragraph("Week Comparison and Compliance", styles["SectionTitle"]))
    story.append(Paragraph(
        f"Week change summary: {placed_count} lines placed on-rent and {removed_count} lines taken off-rent. "
        f"Compliance totals in scope: verified {verified_count}, late {late_count}, pending {pending_count}.",
        styles["BodySmall"],
    ))
    story.append(Image(chart_comparison(), width=6.9 * inch, height=2.1 * inch))

    story.append(Spacer(1, 0.08 * inch))
    story.append(section_divider())
    story.append(Paragraph("Rent-vs-Buy Opportunities", styles["SectionTitle"]))
    story.append(Paragraph(
        f"There are {len(rvb_candidates)} lines where renting is no longer cost-effective under the current filter scope. "
        "The chart below ranks highest estimated monthly savings from ownership.",
        styles["BodySmall"],
    ))
    if rvb_candidates:
        story.append(Image(chart_rvb(), width=6.9 * inch, height=2.45 * inch))
    else:
        story.append(Paragraph("No rent-vs-buy candidates found in this filter scope.", styles["BodySmall"]))

    doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=analytics_synopsis_report.pdf"
    return response


@login_required
def analytics_dashboard(request):
    user = request.user
    profile = _get_profile(user)

    if _is_vendor(user) or not profile or profile.role != "junior_superuser":
        return HttpResponseForbidden(
            "Access denied. The analytics dashboard is restricted to reviewer operations staff."
        )

    master_qs = RentalMaster.objects.filter(is_active=True)
    audit_qs = VendorAudit.objects.all()

    daily_cost_expr = ExpressionWrapper(
        F("rate_daily") * F("quantity"), output_field=DecimalField()
    )

    # Chart 0 — Cost over time (weekly totals across all vendors)
    cost_over_time_data = list(
        master_qs
        .values("cycle_year", "cycle_week")
        .annotate(total=Sum(daily_cost_expr), total_qty=Sum("quantity"))
        .order_by("cycle_year", "cycle_week")
    )
    # Build ISO week labels like "2026-W14"
    cost_over_time_json = json.dumps([
        {
            "label": f"{d['cycle_year']}-W{d['cycle_week']:02d}",
            "monthly": float(d["total"] or 0),
            "quantity": int(d["total_qty"] or 0),
        }
        for d in cost_over_time_data
        if d["cycle_year"] and d["cycle_week"]
    ])
    volume_over_time_json = json.dumps([
        {
            "label": f"{d['cycle_year']}-W{d['cycle_week']:02d}",
            "quantity": int(d["total_qty"] or 0),
        }
        for d in cost_over_time_data
        if d["cycle_year"] and d["cycle_week"]
    ])

    # Comparison tab — latest published week vs the week immediately before it
    available_cycles = [
        (d["cycle_year"], d["cycle_week"])
        for d in cost_over_time_data
        if d["cycle_year"] and d["cycle_week"]
    ]
    comparison_json = json.dumps({
        "current_label": "",
        "previous_label": "",
        "placed_on_rent": [],
        "taken_off_rent": [],
    })
    if len(available_cycles) >= 2:
        prev_year, prev_week = available_cycles[-2]
        curr_year, curr_week = available_cycles[-1]

        previous_rows = list(
            master_qs
            .filter(cycle_year=prev_year, cycle_week=prev_week)
            .values("vendor_name", "equipment_id", "equipment_description", "rate_daily", "quantity")
        )
        current_rows = list(
            master_qs
            .filter(cycle_year=curr_year, cycle_week=curr_week)
            .values("vendor_name", "equipment_id", "equipment_description", "rate_daily", "quantity")
        )

        previous_keys = {
            (row["vendor_name"], row["equipment_id"]): row
            for row in previous_rows
        }
        current_keys = {
            (row["vendor_name"], row["equipment_id"]): row
            for row in current_rows
        }

        placed_on_rent = []
        for key, row in current_keys.items():
            if key not in previous_keys:
                placed_on_rent.append({
                    "vendor_name": row["vendor_name"],
                    "equipment_id": row["equipment_id"],
                    "equipment_description": row["equipment_description"],
                    "monthly_rate": float(row["rate_daily"] or 0) * (row["quantity"] or 0),
                })

        taken_off_rent = []
        for key, row in previous_keys.items():
            if key not in current_keys:
                taken_off_rent.append({
                    "vendor_name": row["vendor_name"],
                    "equipment_id": row["equipment_id"],
                    "equipment_description": row["equipment_description"],
                    "monthly_rate": float(row["rate_daily"] or 0) * (row["quantity"] or 0),
                })

        comparison_json = json.dumps({
            "current_label": f"{curr_year}-W{curr_week:02d}",
            "previous_label": f"{prev_year}-W{prev_week:02d}",
            "placed_on_rent": sorted(placed_on_rent, key=lambda r: (r["vendor_name"], r["equipment_id"])),
            "taken_off_rent": sorted(taken_off_rent, key=lambda r: (r["vendor_name"], r["equipment_id"])),
        })

    # Chart 1 — Spend by vendor (monthly totals; period conversion is done client-side)
    spend_data = list(
        master_qs
        .values("vendor_name")
        .annotate(total=Sum(daily_cost_expr))
        .order_by("-total")[:20]
    )
    spend_json = json.dumps([
        {"vendor": d["vendor_name"], "monthly": float(d["total"] or 0)}
        for d in spend_data
    ])

    # Chart 2 — Compliance by vendor
    compliance_data = list(
        audit_qs
        .values("vendor_name")
        .annotate(
            total=Count("id"),
            verified_count=Count("id", filter=Q(verified=True)),
            late_count=Count("id", filter=Q(is_late=True)),
        )
        .order_by("vendor_name")
    )
    vendors = [d["vendor_name"] for d in compliance_data]
    fig_compliance = go.Figure()
    fig_compliance.add_trace(go.Bar(
        name="Verified",
        x=vendors,
        y=[d["verified_count"] for d in compliance_data],
        marker_color="#1f8a57",
    ))
    fig_compliance.add_trace(go.Bar(
        name="Late",
        x=vendors,
        y=[d["late_count"] for d in compliance_data],
        marker_color="#c0392b",
    ))
    fig_compliance.add_trace(go.Bar(
        name="Pending",
        x=vendors,
        y=[d["total"] - d["verified_count"] - d["late_count"] for d in compliance_data],
        marker_color="#e67e22",
    ))
    fig_compliance.update_layout(
        barmode="stack",
        title="Vendor Submission Compliance by Cycle",
        xaxis_title="Vendor",
        yaxis_title="Submission Count",
        xaxis_tickangle=-35,
        plot_bgcolor="#f3f7fb",
        paper_bgcolor="white",
        font=dict(family="Segoe UI, Helvetica Neue, Arial, sans-serif"),
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=60, r=20, t=70, b=130),
    )

    # Chart 3 — Equipment utilization (top 15 by quantity)
    utilization_data = list(
        master_qs
        .values("equipment_description")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")[:15]
    )
    fig_utilization = go.Figure(go.Bar(
        x=[d["equipment_description"] for d in utilization_data],
        y=[d["total_qty"] or 0 for d in utilization_data],
        marker_color="#195f9d",
        hovertemplate="%{x}<br>Qty: %{y}<extra></extra>",
    ))
    fig_utilization.update_layout(
        title="Top 15 Equipment Lines by Active Quantity On-Rent",
        xaxis_title="Equipment",
        yaxis_title="Total Quantity",
        xaxis_tickangle=-40,
        plot_bgcolor="#f3f7fb",
        paper_bgcolor="white",
        font=dict(family="Segoe UI, Helvetica Neue, Arial, sans-serif"),
        margin=dict(l=60, r=20, t=50, b=170),
    )

    # Table 4 — Rent-vs-buy candidate lines
    # Use the most recent published week as the "current rate" snapshot
    from django.db.models import Max
    latest = (
        RentalMaster.objects.filter(is_active=True)
        .aggregate(week=Max("cycle_week"), year=Max("cycle_year"))
    )
    latest_week = latest["week"] or 0
    latest_year = latest["year"] or 0

    # Pull all latest-week active rows so candidates can be computed dynamically.
    rvb_source_rows = list(
        RentalMaster.objects
        .filter(is_active=True, cycle_week=latest_week, cycle_year=latest_year)
        .values("vendor_name", "equipment_id", "equipment_description", "equipment_category",
                "vendor_code", "po_number", "cycle_year", "cycle_week",
                "rate_daily", "quantity",
                "on_rent_start", "on_rent_end")
        .order_by("-rate_daily")
    )

    # Estimated purchase price + maintenance from EquipmentMarketRate
    market_lookup = {}
    for m in EquipmentMarketRate.objects.order_by("equipment_description", "-effective_date"):
        if m.equipment_description not in market_lookup:
            market_lookup[m.equipment_description] = {
                "est_purchase_price":   float(m.estimated_purchase_price),
                "monthly_maintenance":  float(m.monthly_maintenance_cost),
                "rvb_monthly_threshold": float(m.rvb_monthly_threshold),
                "annual_maint_pct":     float(m.annual_maintenance_pct),
            }

    today = datetime.date.today()

    def _months_on_rent(start, end):
        """Whole + fractional months from start to min(end, today)."""
        if not start:
            return 0.0
        through = min(end, today) if end else today
        if through < start:
            return 0.0
        whole = (through.year - start.year) * 12 + (through.month - start.month)
        # add partial month fraction based on days into current billing month
        import calendar
        days_in_month = calendar.monthrange(through.year, through.month)[1]
        fraction = through.day / days_in_month
        return max(0.0, whole + fraction)

    # Include only rows where renting is no longer cost-effective (monthly rent > threshold).
    rvb_rows = []
    po_dept_map = dict(PODepartment.objects.values_list("po_number", "department"))
    for row in rvb_source_rows:
        mkt = market_lookup.get(row["equipment_description"])
        if mkt is None:
            continue

        monthly_rent = float(row["rate_daily"] or 0) * (row["quantity"] or 0)
        threshold = float(mkt["rvb_monthly_threshold"] or 0)
        if monthly_rent <= threshold:
            continue

        months = _months_on_rent(row["on_rent_start"], row["on_rent_end"])
        maint = mkt["monthly_maintenance"]
        overage = monthly_rent - threshold
        pct_over = (overage / threshold * 100) if threshold else 0
        break_even_months = (mkt["est_purchase_price"] / monthly_rent) if monthly_rent else 0

        row["months_on_rent"] = round(months, 1)
        row["total_paid"] = float(row["rate_daily"]) * row["quantity"] * months
        row["est_purchase_price"] = mkt["est_purchase_price"]
        row["monthly_maintenance"] = maint
        row["annual_maint_pct"] = round(mkt["annual_maint_pct"] * 100, 0)
        row["rvb_candidate"] = True
        row["estimated_monthly_savings"] = overage
        row["vendor_code"] = row.get("vendor_code") or ""
        row["mill_department"] = po_dept_map.get(row.get("po_number") or "", "Unassigned")
        row["po_number"] = row.get("po_number") or ""
        row["cycle_year"] = row.get("cycle_year") or 0
        row["cycle_week"] = row.get("cycle_week") or 0
        row["reasoning"] = (
            f"At ${monthly_rent:,.0f}/mo this unit costs "
            f"${overage:,.0f} ({pct_over:.0f}%) more per month than owning it would. "
            f"Purchasing at ${mkt['est_purchase_price']:,.0f} with ~${maint:,.0f}/mo "
            f"in maintenance would break even in roughly "
            f"{break_even_months:.1f} months. "
            f"Strongly consider purchasing."
        )
        rvb_rows.append(row)

    rvb_rows.sort(key=lambda r: r.get("estimated_monthly_savings", 0), reverse=True)
    rvb_rows = rvb_rows[:25]

    # Distinct (year, week) pairs available in master for the week picker
    available_weeks = list(
        RentalMaster.objects
        .filter(is_active=True)
        .values("cycle_year", "cycle_week")
        .distinct()
        .order_by("-cycle_year", "-cycle_week")
    )

    latest_year = 0
    latest_week = 0
    latest_equipment_count = 0
    latest_monthly_total = 0.0
    latest_weekly_total = 0.0
    if available_weeks:
        latest_year = available_weeks[0]["cycle_year"] or 0
        latest_week = available_weeks[0]["cycle_week"] or 0
        latest_qs = master_qs.filter(cycle_year=latest_year, cycle_week=latest_week)
        latest_equipment_count = (
            latest_qs.aggregate(total_qty=Sum("quantity"))["total_qty"] or 0
        )
        latest_monthly_total = float(
            latest_qs.aggregate(total_cost=Sum(daily_cost_expr))["total_cost"] or 0
        )
        latest_weekly_total = latest_monthly_total * 0.25

    context = {
        "cost_over_time_json": cost_over_time_json,
        "volume_over_time_json": volume_over_time_json,
        "comparison_json": comparison_json,
        "spend_json": spend_json,
        "compliance_chart": json.dumps(fig_compliance, cls=PlotlyJSONEncoder),
        "utilization_chart": json.dumps(fig_utilization, cls=PlotlyJSONEncoder),
        "rvb_rows": rvb_rows,
        "spend_data_count": len(spend_data),
        "available_weeks": available_weeks,
        "latest_year": latest_year,
        "latest_week": latest_week,
        "latest_equipment_count": latest_equipment_count,
        "latest_weekly_total": latest_weekly_total,
        "latest_monthly_total": latest_monthly_total,
        "approved_categories_json": json.dumps(
            list(ApprovedEquipmentCategory.objects.values_list("name", flat=True))
        ),
    }
    return render(request, "rentals/analytics.html", context)


@login_required
def analytics_rows(request):
    """Lightweight JSON endpoint — returns all dashboard rows for async hydration."""
    user = request.user
    profile = _get_profile(user)
    if _is_vendor(user) or not profile or profile.role != "junior_superuser":
        return JsonResponse({"error": "forbidden"}, status=403)

    master_qs = RentalMaster.objects.filter(is_active=True)
    po_dept_map = dict(PODepartment.objects.values_list("po_number", "department"))

    dashboard_rows = []
    for row in (
        master_qs
        .order_by("-cycle_year", "-cycle_week", "vendor_name", "equipment_id")
        .values(
            "cycle_year", "cycle_week", "equipment_id", "vendor_name",
            "vendor_code", "equipment_description", "equipment_category",
            "po_number", "quantity", "rate_daily",
            "on_rent_start", "on_rent_end", "sn_request_number",
            "approved_by__username",
        )
    ):
        cycle_year = row["cycle_year"]
        cycle_week = row["cycle_week"]
        if not cycle_year or not cycle_week:
            continue
        qty = int(row["quantity"] or 0)
        rate = float(row["rate_daily"] or 0)
        po = row["po_number"] or ""
        start = row["on_rent_start"]
        end = row["on_rent_end"]
        dashboard_rows.append({
            "cycle_year": int(cycle_year),
            "cycle_week": int(cycle_week),
            "equipment_id": row["equipment_id"] or "",
            "vendor_name": row["vendor_name"] or "",
            "vendor_code": row["vendor_code"] or "Unassigned",
            "mill_department": po_dept_map.get(po, "Unassigned"),
            "equipment_description": row["equipment_description"] or "Unknown",
            "equipment_category": row["equipment_category"] or "Uncategorized",
            "po_number": po,
            "quantity": qty,
            "monthly": rate * qty,
            "rate_daily": rate,
            "on_rent_start": start.strftime("%m/%d/%Y") if start else "",
            "on_rent_end": end.strftime("%m/%d/%Y") if end else "",
            "sn_request_number": row["sn_request_number"] or "",
            "approved_by": row["approved_by__username"] or "",
        })

    return JsonResponse({"rows": dashboard_rows})


# ─────────────────────────────────────────────
#  VENDOR PORTAL VIEWS
# ─────────────────────────────────────────────

def _vendor_company_name(user):
    profile = _get_profile(user)
    if profile and profile.company:
        return profile.company.name
    return None


@login_required
def vendor_dashboard(request):
    user = request.user
    profile = _get_profile(user)

    if not profile or profile.role != "vendor":
        return redirect("/admin/")

    company_name = _vendor_company_name(user)

    # Determine current ISO week first — staging is scoped to current week only.
    # Showing all historical staging rows (seeded for weeks 1-17) causes
    # thousands of DOM nodes and makes the browser unresponsive.
    today = datetime.date.today()
    iso = today.isocalendar()
    current_week = iso[1]
    current_year = iso[0]
    current_cycle_date = datetime.date.fromisocalendar(current_year, current_week, 1)

    staging_qs = (
        RentalStaging.objects.filter(
            vendor_name=company_name,
            cycle_week=current_week,
            cycle_year=current_year,
        ).order_by("equipment_id")
        if company_name
        else RentalStaging.objects.none()
    )

    # Auto-seed current-week staging from the vendor's last published week in
    # RentalMaster if they have no rows yet and the submission window is still open.
    # This gives every vendor a pre-populated starting point — they just update
    # what changed from last week rather than re-entering everything from scratch.
    _window_already_closed = RentalMaster.objects.filter(
        cycle_week=current_week, cycle_year=current_year
    ).exists()
    if company_name and not staging_qs.exists() and not _window_already_closed:
        _seed_ref = (
            RentalMaster.objects
            .filter(vendor_name=company_name, is_active=True)
            .order_by("-cycle_year", "-cycle_week")
            .values("cycle_year", "cycle_week")
            .first()
        )
        if _seed_ref:
            _prior_master = list(
                RentalMaster.objects.filter(
                    vendor_name=company_name,
                    is_active=True,
                    cycle_week=_seed_ref["cycle_week"],
                    cycle_year=_seed_ref["cycle_year"],
                )
            )
            if _prior_master:
                RentalStaging.objects.bulk_create([
                    RentalStaging(
                        vendor_name=company_name,
                        vendor_code=m.vendor_code,
                        equipment_id=m.equipment_id,
                        equipment_description=m.equipment_description,
                        equipment_category=m.equipment_category,
                        quantity=m.quantity,
                        rate_daily=m.rate_daily,
                        on_rent_start=m.on_rent_start,
                        on_rent_end=m.on_rent_end,
                        po_number=m.po_number,
                        sn_request_number=m.sn_request_number,
                        comments=m.comments,
                        cycle_week=current_week,
                        cycle_year=current_year,
                        status=SubmissionStatus.PENDING,
                        submitted_by=None,
                        is_validated=False,
                    )
                    for m in _prior_master
                ])

    staging_rows = list(staging_qs)

    # Approved categories for the Add Row dropdown — admin-managed
    equipment_categories = list(
        ApprovedEquipmentCategory.objects.values_list("name", flat=True)
    )
    equipment_categories_json = json.dumps(equipment_categories)

    # Audit record for the current week only — if none exists, the vendor hasn't submitted yet
    audit = (
        VendorAudit.objects.filter(vendor_name=company_name, cycle_date=current_cycle_date)
        .first()
    )

    # Submission window is open from Monday 00:00 of the current week until the
    # reviewer publishes that week's data to RentalMaster.  Once published, no
    # further vendor submissions are accepted.
    window_closed = RentalMaster.objects.filter(
        cycle_week=current_week, cycle_year=current_year
    ).exists()

    # Find the nearest future audit so we can tell the vendor when the next
    # window opens (covers both "Sunday before the week starts" and
    # "current week published/verified — nothing left to do").
    next_audit = (
        VendorAudit.objects
        .filter(vendor_name=company_name, cycle_date__gt=current_cycle_date)
        .order_by("cycle_date")
        .first()
    )
    # Show the "caught up" banner when there is nothing actionable right now
    # but a future cycle is already on record.
    done_for_now = (
        (audit is None or (audit.verified and window_closed))
        and next_audit is not None
    )

    # Collect any Django messages (success/error from edit / no-change actions)
    msg_list = messages.get_messages(request)

    context = {
        "staging_rows": staging_rows,
        "equipment_categories": equipment_categories,
        "equipment_categories_json": equipment_categories_json,
        "audit": audit,
        "company_name": company_name,
        "today": today,
        "current_week": current_week,
        "current_year": current_year,
        "window_closed": window_closed,
        "done_for_now": done_for_now,
        "next_audit": next_audit,
        "msg_list": msg_list,
        "session_key": request.session.session_key or "",
    }
    return render(request, "rentals/vendor_dashboard.html", context)


@login_required
def vendor_edit_row(request, pk):
    user = request.user
    profile = _get_profile(user)

    if not profile or profile.role != "vendor":
        return redirect("/admin/")

    company_name = _vendor_company_name(user)
    row = get_object_or_404(RentalStaging, pk=pk, vendor_name=company_name)

    errors = {}

    if request.method == "POST":
        # Collect POSTed values
        eq_desc = request.POST.get("equipment_description", "").strip()
        qty_raw = request.POST.get("quantity", "").strip()
        rate_raw = request.POST.get("rate_daily", "").strip()
        start_raw = request.POST.get("on_rent_start", "").strip()
        end_raw = request.POST.get("on_rent_end", "").strip()

        # Validate
        if not eq_desc:
            errors["equipment_description"] = "Description is required."

        qty = None
        try:
            qty = int(qty_raw)
            if qty < 1:
                errors["quantity"] = "Quantity must be at least 1."
        except (ValueError, TypeError):
            errors["quantity"] = "Enter a valid whole number."

        import decimal
        rate = None
        try:
            rate = decimal.Decimal(rate_raw)
            if rate <= 0:
                errors["rate_daily"] = "Daily rate must be greater than zero."
        except (decimal.InvalidOperation, ValueError):
            errors["rate_daily"] = "Enter a valid dollar amount (e.g. 125.00)."

        start_date = None
        try:
            start_date = datetime.date.fromisoformat(start_raw)
        except (ValueError, TypeError):
            errors["on_rent_start"] = "Enter a valid date (YYYY-MM-DD)."

        end_date = None
        if end_raw:
            try:
                end_date = datetime.date.fromisoformat(end_raw)
                if start_date and end_date < start_date:
                    errors["on_rent_end"] = "End date cannot be before start date."
            except (ValueError, TypeError):
                errors["on_rent_end"] = "Enter a valid date (YYYY-MM-DD)."

        if not errors:
            row.equipment_description = eq_desc
            row.quantity = qty
            row.rate_daily = rate
            row.on_rent_start = start_date
            row.on_rent_end = end_date
            row.save()
            messages.success(request, f"Record \"{row.equipment_id}\" updated successfully.")
            return redirect("vendor_dashboard")

    context = {
        "row": row,
        "company_name": company_name,
        "errors": errors,
    }
    return render(request, "rentals/vendor_edit.html", context)


@login_required
def vendor_declare_no_change(request):
    if request.method != "POST":
        return redirect("vendor_dashboard")

    user = request.user
    profile = _get_profile(user)

    if not profile or profile.role != "vendor":
        return redirect("/admin/")

    company_name = _vendor_company_name(user)
    _today = datetime.date.today()
    _iso = _today.isocalendar()
    _cycle_date = datetime.date.fromisocalendar(_iso[0], _iso[1], 1)

    if RentalMaster.objects.filter(cycle_week=_iso[1], cycle_year=_iso[0]).exists():
        messages.error(request, "The submission window for this week has closed — the reviewer has already published.")
        return redirect("vendor_dashboard")

    audit = VendorAudit.objects.filter(vendor_name=company_name, cycle_date=_cycle_date).first()

    if not audit:
        messages.error(request, "No active audit cycle is open for this week. Please contact your administrator.")
        return redirect("vendor_dashboard")

    if audit.verified:
        messages.warning(request, "This cycle is already marked as verified.")
        return redirect("vendor_dashboard")

    audit.no_change = True  # default: no changes
    if request.POST.get("has_changes") == "1":
        audit.no_change = False
    audit.no_change_declared_at = timezone.now()
    audit.verified = True
    audit.submitted_at = timezone.now()
    audit.save(update_fields=["no_change", "no_change_declared_at", "verified", "submitted_at", "updated_at"])

    # Stamp only the current week's staging rows — do not touch historical staging.
    cycle_iso = audit.cycle_date.isocalendar()
    RentalStaging.objects.filter(
        vendor_name=company_name,
        cycle_week=cycle_iso[1],
        cycle_year=cycle_iso[0],
    ).update(
        cycle_week=cycle_iso[1],
        cycle_year=cycle_iso[0],
    )

    if audit.no_change:
        msg = f"Confirmed: No changes this week for cycle {audit.cycle_date}. Submission complete."
    else:
        msg = f"Week {audit.cycle_date} rental data submitted successfully."
    messages.success(request, msg)
    return redirect("vendor_dashboard")


@login_required
@require_POST
def vendor_validate_staging(request):
    """
    AJAX endpoint — validates all staging rows for the current vendor/cycle
    and returns a list of per-row errors without committing anything.
    Called by the submit modal before the final form POST.
    """
    import re as _re
    from decimal import Decimal, InvalidOperation

    user = request.user
    profile = _get_profile(user)
    if not profile or profile.role != "vendor":
        return JsonResponse({"ok": False, "error": "Unauthorized."}, status=403)

    company_name = _vendor_company_name(user)
    approved_categories = set(
        ApprovedEquipmentCategory.objects.values_list("name", flat=True)
    )

    # PO must be non-empty and match PO-<digits>[-<digits>]* pattern
    PO_RE = _re.compile(r'^PO-\d+(-\d+)*$', _re.IGNORECASE)
    # Date stored as Python date — no format issues from DB, but rate/description
    # can be mangled by inline edits.

    rows = (
        RentalStaging.objects
        .filter(
            vendor_name=company_name,
            cycle_week=datetime.date.today().isocalendar()[1],
            cycle_year=datetime.date.today().isocalendar()[0],
        )
        .order_by("equipment_id")
    )

    row_errors = []
    for idx, row in enumerate(rows, start=1):
        errors = []

        # Equipment ID
        if not (row.equipment_id or "").strip():
            errors.append("Equipment ID is required.")

        # Description
        if not (row.equipment_description or "").strip():
            errors.append("Description is required.")

        # Category — must be in approved list
        cat = (row.equipment_category or "").strip()
        if not cat:
            errors.append("Category is required — select from the approved list.")
        elif approved_categories and cat not in approved_categories:
            errors.append(
                f'Category "{cat}" is not in the approved list. '
                f'Choose from: {", ".join(sorted(approved_categories))}.'
            )

        # Monthly rate — must be > 0
        try:
            if row.rate_daily is None or Decimal(str(row.rate_daily)) <= 0:
                errors.append("Monthly rate must be greater than $0.00.")
        except InvalidOperation:
            errors.append(f'Monthly rate "{row.rate_daily}" is not a valid dollar amount.')

        # On-rent start — required, must be a real date
        if not row.on_rent_start:
            errors.append("On Rent Start date is required.")

        # On-rent end — if present must be >= start
        if row.on_rent_end and row.on_rent_start and row.on_rent_end < row.on_rent_start:
            errors.append(
                f"On Rent End ({row.on_rent_end}) cannot be before On Rent Start ({row.on_rent_start})."
            )

        # PO number — required and must match pattern
        po = (row.po_number or "").strip()
        if not po:
            errors.append("PO # is required.")
        elif not PO_RE.match(po):
            errors.append(
                f'PO # "{po}" is not a valid format. Expected format: PO-NNNNN or PO-YYYY-NNNN.'
            )

        if errors:
            row_errors.append({
                "row": idx,
                "equipment_id": row.equipment_id or "—",
                "errors": errors,
            })

    if row_errors:
        return JsonResponse({"ok": False, "row_errors": row_errors})
    return JsonResponse({"ok": True})


@login_required
@require_POST
def vendor_no_change_ajax(request):
    """
    AJAX endpoint for the welcome modal's 'No' button.
    Marks the current audit cycle as no-change/verified and returns JSON.
    """
    user = request.user
    profile = _get_profile(user)

    if not profile or profile.role != "vendor":
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=403)

    company_name = _vendor_company_name(user)
    _today = datetime.date.today()
    _iso = _today.isocalendar()
    _cycle_date = datetime.date.fromisocalendar(_iso[0], _iso[1], 1)

    if RentalMaster.objects.filter(cycle_week=_iso[1], cycle_year=_iso[0]).exists():
        return JsonResponse({"ok": False, "error": "The submission window has closed — the reviewer has already published this week."}, status=400)

    audit = VendorAudit.objects.filter(vendor_name=company_name, cycle_date=_cycle_date).first()

    if not audit:
        return JsonResponse({"ok": False, "error": "No active audit cycle is open for this week."}, status=400)

    if audit.verified:
        return JsonResponse({"ok": True, "already_verified": True})

    audit.no_change = True
    audit.no_change_declared_at = timezone.now()
    audit.verified = True
    audit.submitted_at = timezone.now()
    audit.save(update_fields=["no_change", "no_change_declared_at", "verified", "submitted_at", "updated_at"])

    # Stamp only current week's staging rows — do not touch historical staging.
    cycle_iso = audit.cycle_date.isocalendar()
    RentalStaging.objects.filter(
        vendor_name=company_name,
        cycle_week=cycle_iso[1],
        cycle_year=cycle_iso[0],
    ).update(
        cycle_week=cycle_iso[1],
        cycle_year=cycle_iso[0],
    )

    return JsonResponse({
        "ok": True,
        "cycle_date": str(audit.cycle_date),
        "week": cycle_iso[1],
    })


# ─── Fields compared week-over-week ───────────────────────────────────────────
_CHANGE_TRACKED_FIELDS = [
    ("equipment_description", "Description"),
    ("equipment_category",    "Category"),
    ("quantity",              "Quantity"),
    ("rate_daily",            "Monthly Rate"),
    ("on_rent_start",         "On Rent Start"),
    ("on_rent_end",           "On Rent End"),
    ("po_number",             "PO #"),
    ("sn_request_number",     "SN Request #"),
]


@login_required
def vendor_change_check(request):
    """AJAX GET — compare vendor's current staging rows against their latest
    published RentalMaster rows for the same equipment IDs.  Returns a JSON
    list of field-level changes so the vendor can review them before submitting.
    """
    profile = _get_profile(request.user)
    if not profile or profile.role != "vendor":
        return JsonResponse({"ok": False, "changes": []}, status=403)

    company_name = _vendor_company_name(request.user)
    _today_vc = datetime.date.today()
    _iso_vc = _today_vc.isocalendar()
    staging_rows = list(RentalStaging.objects.filter(
        vendor_name=company_name,
        cycle_week=_iso_vc[1],
        cycle_year=_iso_vc[0],
    ))

    # Build map: equipment_id → most recent published master row for this vendor
    master_by_eq: dict = {}
    for m in (RentalMaster.objects
              .filter(vendor_name=company_name, is_active=True)
              .order_by("equipment_id", "-cycle_year", "-cycle_week")):
        if m.equipment_id not in master_by_eq:
            master_by_eq[m.equipment_id] = m

    changes = []
    for s in staging_rows:
        m = master_by_eq.get(s.equipment_id)
        if not m:
            continue  # new equipment — no prior history to diff
        for field, label in _CHANGE_TRACKED_FIELDS:
            old_val = getattr(m, field)
            new_val = getattr(s, field)
            old_str = str(old_val) if old_val is not None else ""
            new_str = str(new_val) if new_val is not None else ""
            if old_str != new_str:
                changes.append({
                    "equipment_id": s.equipment_id,
                    "field":        label,
                    "old":          old_str,
                    "new":          new_str,
                })

    return JsonResponse({"ok": True, "changes": changes})


@login_required
def reviewer_change_check(request):
    """AJAX GET — compare all submitted staging rows for a given cycle week
    against the most recent prior published RentalMaster rows for the same
    vendor + equipment_id pairs.  Used by the reviewer before publishing.
    """
    profile = _get_profile(request.user)
    if not profile or profile.role != "junior_superuser":
        return JsonResponse({"ok": False, "changes": []}, status=403)

    try:
        week = int(request.GET.get("week", 0))
        year = int(request.GET.get("year", 0))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "changes": []}, status=400)

    staging_rows = list(RentalStaging.objects.filter(
        cycle_week=week,
        cycle_year=year,
        status=SubmissionStatus.SUBMITTED,
    ))

    # Build lookup: (vendor_name, equipment_id) → latest prior-cycle master row
    pairs = {(s.vendor_name, s.equipment_id) for s in staging_rows}
    master_by_pair: dict = {}
    for vendor_name, equipment_id in pairs:
        m = (RentalMaster.objects
             .filter(vendor_name=vendor_name, equipment_id=equipment_id, is_active=True)
             .exclude(cycle_week=week, cycle_year=year)
             .order_by("-cycle_year", "-cycle_week")
             .first())
        if m:
            master_by_pair[(vendor_name, equipment_id)] = m

    changes = []
    for s in staging_rows:
        m = master_by_pair.get((s.vendor_name, s.equipment_id))
        if not m:
            continue
        for field, label in _CHANGE_TRACKED_FIELDS:
            old_val = getattr(m, field)
            new_val = getattr(s, field)
            old_str = str(old_val) if old_val is not None else ""
            new_str = str(new_val) if new_val is not None else ""
            if old_str != new_str:
                changes.append({
                    "vendor":       s.vendor_name,
                    "equipment_id": s.equipment_id,
                    "field":        label,
                    "old":          old_str,
                    "new":          new_str,
                })

    return JsonResponse({"ok": True, "changes": changes})


@login_required
@require_POST
def vendor_csv_upload(request):
    """
    AJAX endpoint — accepts a multipart CSV upload from the vendor welcome modal.
    Validates headers and every data row, then overwrites staging data for the
    current cycle.  Returns JSON with detailed per-row errors on failure.
    """
    import csv as csv_mod
    import io
    from decimal import Decimal, InvalidOperation

    user = request.user
    profile = _get_profile(user)
    if not profile or profile.role != "vendor":
        return JsonResponse({"ok": False, "error": "Unauthorized."}, status=403)

    company_name = _vendor_company_name(user)
    _today = datetime.date.today()
    _iso = _today.isocalendar()
    _cycle_date = datetime.date.fromisocalendar(_iso[0], _iso[1], 1)

    if RentalMaster.objects.filter(cycle_week=_iso[1], cycle_year=_iso[0]).exists():
        return JsonResponse({"ok": False, "error": "The submission window has closed — the reviewer has already published this week."}, status=400)

    audit = VendorAudit.objects.filter(vendor_name=company_name, cycle_date=_cycle_date).first()
    if not audit:
        return JsonResponse({"ok": False, "error": "No active audit cycle is open for this week."}, status=400)
    if audit.verified:
        return JsonResponse({"ok": False, "error": "This cycle is already verified."}, status=400)

    csv_file = request.FILES.get("csv_file")
    if not csv_file:
        return JsonResponse({"ok": False, "error": "No file was uploaded."}, status=400)

    # Decode — accept UTF-8 with or without BOM
    try:
        text = csv_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return JsonResponse(
            {"ok": False, "error": "File could not be decoded. Please save as CSV (UTF-8)."},
            status=400,
        )

    reader = csv_mod.DictReader(io.StringIO(text))

    # ── Header validation ──────────────────────────────────────────────────
    REQUIRED_HEADERS = {"EQUIPMENT #", "DESCRIPTION", "RENT START", "MO. RATE $"}
    EXPECTED_HEADERS = {
        "YEAR", "WK #", "RENTAL CO.", "TYPE OF EQUIP.", "EQUIPMENT #",
        "DESCRIPTION", "RENT START", "PROJ. END", "PO #", "SN REQ #",
        "MO. RATE $", "COMMENTS", "PUBLISHED BY",
    }

    raw_fieldnames = reader.fieldnames or []
    actual_headers = {h.strip() for h in raw_fieldnames}

    missing_required = REQUIRED_HEADERS - actual_headers
    unexpected = actual_headers - EXPECTED_HEADERS

    header_errors = []
    if missing_required:
        header_errors.append(
            f"Missing required column(s): {', '.join(sorted(missing_required))}"
        )
    if unexpected:
        header_errors.append(
            f"Unrecognised column(s): {', '.join(sorted(unexpected))}. "
            f"Allowed columns: {', '.join(sorted(EXPECTED_HEADERS))}"
        )
    if header_errors:
        return JsonResponse({"ok": False, "header_errors": header_errors, "row_errors": []})

    # ── Row validation ─────────────────────────────────────────────────────
    approved_categories = set(
        ApprovedEquipmentCategory.objects.values_list("name", flat=True)
    )

    def _parse_date(raw):
        for fmt in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
        return None

    valid_rows = []
    row_errors = []

    for row_num, row in enumerate(reader, start=2):  # row 1 is the header
        r = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
        errors = []

        # equipment_id
        equipment_id = r.get("EQUIPMENT #", "")
        if not equipment_id:
            errors.append("EQUIPMENT # is required.")

        # description
        description = r.get("DESCRIPTION", "")
        if not description:
            errors.append("DESCRIPTION is required.")

        # on_rent_start
        start_raw = r.get("RENT START", "")
        on_rent_start = None
        if not start_raw:
            errors.append("RENT START is required.")
        else:
            on_rent_start = _parse_date(start_raw)
            if on_rent_start is None:
                errors.append(
                    f"RENT START \"{start_raw}\" is not a valid date (expected MM/DD/YYYY)."
                )

        # on_rent_end
        end_raw = r.get("PROJ. END", "")
        on_rent_end = None
        if end_raw and end_raw not in ("—", "-", "N/A"):
            on_rent_end = _parse_date(end_raw)
            if on_rent_end is None:
                errors.append(
                    f"PROJ. END \"{end_raw}\" is not a valid date (expected MM/DD/YYYY or blank)."
                )
            elif on_rent_start and on_rent_end < on_rent_start:
                errors.append(
                    f"PROJ. END ({end_raw}) cannot be before RENT START ({start_raw})."
                )

        # rate (monthly rate stored in rate_daily field)
        rate_raw = r.get("MO. RATE $", "")
        rate = None
        if not rate_raw or rate_raw in ("—", "-"):
            errors.append("MO. RATE $ is required.")
        else:
            cleaned = rate_raw.replace("$", "").replace(",", "").strip()
            try:
                rate = Decimal(cleaned)
                if rate <= 0:
                    errors.append(f"MO. RATE $ must be greater than zero (got \"{rate_raw}\").")
            except InvalidOperation:
                errors.append(f"MO. RATE $ \"{rate_raw}\" is not a valid dollar amount.")

        # equipment category — required; must be in approved list if list is populated
        category = r.get("TYPE OF EQUIP.", "").strip()
        if not category:
            errors.append("TYPE OF EQUIP. is required and cannot be blank.")
        elif approved_categories and category not in approved_categories:
            errors.append(
                f"TYPE OF EQUIP. \"{category}\" is not in the approved categories list."
            )

        # vendor name — if RENTAL CO. is present it must match
        rental_co = r.get("RENTAL CO.", "")
        if rental_co and rental_co != company_name:
            errors.append(
                f"RENTAL CO. \"{rental_co}\" does not match your company (\"{company_name}\")."
            )

        if errors:
            row_errors.append({"row": row_num, "errors": errors})
        else:
            valid_rows.append({
                "equipment_id": equipment_id,
                "equipment_description": description,
                "quantity": 1,
                "rate_daily": rate,
                "on_rent_start": on_rent_start,
                "on_rent_end": on_rent_end,
                "po_number": r.get("PO #", ""),
                "sn_request_number": r.get("SN REQ #", ""),
                "comments": r.get("COMMENTS", ""),
                "equipment_category": category,
            })

    if row_errors:
        return JsonResponse({"ok": False, "header_errors": [], "row_errors": row_errors})

    if not valid_rows:
        return JsonResponse(
            {"ok": False, "error": "The CSV file contains no data rows."},
            status=400,
        )

    # ── Overwrite staging data ─────────────────────────────────────────────
    from django.db import transaction as db_tx

    cycle_iso = audit.cycle_date.isocalendar()
    with db_tx.atomic():
        # Delete only the current week's staging for this vendor.
        # Historical staging rows (from seeded prior weeks) must not be touched.
        RentalStaging.objects.filter(
            vendor_name=company_name,
            cycle_week=cycle_iso[1],
            cycle_year=cycle_iso[0],
        ).delete()
        RentalStaging.objects.bulk_create([
            RentalStaging(
                vendor_name=company_name,
                equipment_id=r["equipment_id"],
                equipment_description=r["equipment_description"],
                quantity=r["quantity"],
                rate_daily=r["rate_daily"],
                on_rent_start=r["on_rent_start"],
                on_rent_end=r["on_rent_end"],
                po_number=r["po_number"],
                sn_request_number=r["sn_request_number"],
                comments=r["comments"],
                equipment_category=r["equipment_category"],
                cycle_week=cycle_iso[1],
                cycle_year=cycle_iso[0],
                status=SubmissionStatus.PENDING,
                submitted_by=user,
                is_validated=True,
            )
            for r in valid_rows
        ])
        # Audit remains unverified — vendor must still click Submit Weekly Report

    return JsonResponse({"ok": True, "count": len(valid_rows), "week": cycle_iso[1]})


@login_required
def vendor_inline_save(request, pk):
    """AJAX endpoint — returns JSON, used by inline table editing."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "errors": {"__all__": "Invalid method."}}, status=405)

    user = request.user
    profile = _get_profile(user)

    if not profile or profile.role != "vendor":
        return JsonResponse({"ok": False, "errors": {"__all__": "Not authorized."}}, status=403)

    company_name = _vendor_company_name(user)
    try:
        row = RentalStaging.objects.get(pk=pk, vendor_name=company_name)
    except RentalStaging.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"__all__": "Record not found."}}, status=404)

    eq_id_raw    = request.POST.get("equipment_id", "").strip()
    eq_desc      = request.POST.get("equipment_description", "").strip()
    category_raw = request.POST.get("equipment_category", "").strip()
    qty_raw      = request.POST.get("quantity", "").strip()
    rate_raw     = request.POST.get("rate_daily", "").strip()
    start_raw    = request.POST.get("on_rent_start", "").strip()
    end_raw      = request.POST.get("on_rent_end", "").strip()
    po_raw       = request.POST.get("po_number", "").strip()
    sn_raw       = request.POST.get("sn_request_number", "").strip()
    comments_raw = request.POST.get("comments", "").strip()

    errors = {}
    if not eq_id_raw:
        errors["equipment_id"] = "Equipment ID is required."
    if not eq_desc:
        errors["equipment_description"] = "Description is required."

    # Category — must be chosen from approved list
    import re as _re
    approved_cats = list(ApprovedEquipmentCategory.objects.values_list("name", flat=True))
    if not category_raw:
        errors["equipment_category"] = "Category is required — select from the dropdown."
    elif approved_cats and category_raw not in approved_cats:
        errors["equipment_category"] = (
            f'"{category_raw}" is not an approved category. Select from the dropdown.'
        )

    # PO number — required and must match PO-<digits> pattern
    PO_RE = _re.compile(r'^PO-\d+(-\d+)*$', _re.IGNORECASE)
    if not po_raw:
        errors["po_number"] = "PO # is required."
    elif not PO_RE.match(po_raw):
        errors["po_number"] = f'PO # "{po_raw}" must match PO-NNNNN or PO-YYYY-NNNN format.'

    if not sn_raw:
        errors["sn_request_number"] = "SN Request # is required."

    qty = None
    try:
        qty = int(qty_raw)
        if qty < 1:
            errors["quantity"] = "Quantity must be at least 1."
    except (ValueError, TypeError):
        errors["quantity"] = "Enter a valid whole number."

    import decimal
    rate = None
    try:
        rate = decimal.Decimal(rate_raw)
        if rate <= 0:
            errors["rate_daily"] = "Daily rate must be greater than zero."
    except (decimal.InvalidOperation, ValueError):
        errors["rate_daily"] = "Enter a valid dollar amount."

    start_date = None
    try:
        start_date = datetime.date.fromisoformat(start_raw)
    except (ValueError, TypeError):
        errors["on_rent_start"] = "Enter a valid date."

    end_date = None
    if end_raw:
        try:
            end_date = datetime.date.fromisoformat(end_raw)
            if start_date and end_date < start_date:
                errors["on_rent_end"] = "End date cannot be before start date."
        except (ValueError, TypeError):
            errors["on_rent_end"] = "Enter a valid date."

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    row.equipment_id           = eq_id_raw
    row.equipment_description = eq_desc
    row.equipment_category    = category_raw
    row.quantity              = qty
    row.rate_daily            = rate
    row.on_rent_start         = start_date
    row.on_rent_end           = end_date
    row.po_number             = po_raw
    row.sn_request_number     = sn_raw
    row.comments              = comments_raw
    row.save()

    return JsonResponse({
        "ok":                    True,
        "equipment_id":          row.equipment_id,
        "equipment_description": row.equipment_description,
        "equipment_category":    row.equipment_category or "",
        "quantity":              row.quantity,
        "rate_daily":            str(row.rate_daily),
        "on_rent_start":         row.on_rent_start.isoformat() if row.on_rent_start else "",
        "on_rent_end":           row.on_rent_end.isoformat()   if row.on_rent_end   else "",
        "po_number":             row.po_number or "",
        "sn_request_number":     row.sn_request_number or "",
        "comments":              row.comments or "",
    })


@login_required
def vendor_delete_row(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "errors": {"__all__": "Invalid method."}}, status=405)
    user = request.user
    profile = _get_profile(user)
    if not profile or profile.role != "vendor":
        return JsonResponse({"ok": False, "errors": {"__all__": "Not authorized."}}, status=403)
    company_name = _vendor_company_name(user)
    try:
        row = RentalStaging.objects.get(pk=pk, vendor_name=company_name)
    except RentalStaging.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"__all__": "Record not found."}}, status=404)
    row.delete()
    return JsonResponse({"ok": True})


@login_required
def vendor_add_row(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "errors": {"__all__": "Invalid method."}}, status=405)
    user = request.user
    profile = _get_profile(user)
    if not profile or profile.role != "vendor":
        return JsonResponse({"ok": False, "errors": {"__all__": "Not authorized."}}, status=403)
    company_name = _vendor_company_name(user)
    if not company_name:
        return JsonResponse({"ok": False, "errors": {"__all__": "No company linked to your account."}}, status=400)

    eq_id_raw    = request.POST.get("equipment_id", "").strip()
    eq_desc      = request.POST.get("equipment_description", "").strip()
    cat_raw      = request.POST.get("equipment_category", "").strip()
    qty_raw      = request.POST.get("quantity", "").strip()
    rate_raw     = request.POST.get("rate_daily", "").strip()
    start_raw    = request.POST.get("on_rent_start", "").strip()
    end_raw      = request.POST.get("on_rent_end", "").strip()
    po_raw       = request.POST.get("po_number", "").strip()
    sn_raw       = request.POST.get("sn_request_number", "").strip()
    comments_raw = request.POST.get("comments", "").strip()

    errors = {}
    if not eq_id_raw:
        errors["equipment_id"] = "Equipment ID is required."
    if not eq_desc:
        errors["equipment_description"] = "Description is required."
    if not cat_raw:
        errors["equipment_category"] = "Category is required."
    if not po_raw:
        errors["po_number"] = "PO # is required."
    if not sn_raw:
        errors["sn_request_number"] = "SN Request # is required."

    qty = None
    try:
        qty = int(qty_raw)
        if qty < 1:
            errors["quantity"] = "Quantity must be at least 1."
    except (ValueError, TypeError):
        errors["quantity"] = "Enter a valid whole number."

    import decimal
    rate = None
    try:
        rate = decimal.Decimal(rate_raw)
        if rate <= 0:
            errors["rate_daily"] = "Monthly rate must be greater than zero."
    except (decimal.InvalidOperation, ValueError):
        errors["rate_daily"] = "Enter a valid dollar amount."

    start_date = None
    try:
        start_date = datetime.date.fromisoformat(start_raw)
    except (ValueError, TypeError):
        errors["on_rent_start"] = "Enter a valid date."

    end_date = None
    if end_raw:
        try:
            end_date = datetime.date.fromisoformat(end_raw)
            if start_date and end_date < start_date:
                errors["on_rent_end"] = "End date cannot be before start date."
        except (ValueError, TypeError):
            errors["on_rent_end"] = "Enter a valid date."

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    row = RentalStaging.objects.create(
        vendor_name=company_name,
        equipment_id=eq_id_raw,
        equipment_description=eq_desc,
        equipment_category=cat_raw,
        quantity=qty,
        rate_daily=rate,
        currency="USD",
        on_rent_start=start_date,
        on_rent_end=end_date,
        po_number=po_raw,
        sn_request_number=sn_raw,
        comments=comments_raw,
        submitted_by=user,
        status="pending",
    )
    return JsonResponse({
        "ok":                    True,
        "pk":                    row.pk,
        "equipment_id":          row.equipment_id,
        "equipment_description": row.equipment_description,
        "equipment_category":    row.equipment_category or "",
        "quantity":              row.quantity,
        "rate_daily":            str(row.rate_daily),
        "on_rent_start":         row.on_rent_start.isoformat() if row.on_rent_start else "",
        "on_rent_end":           row.on_rent_end.isoformat()   if row.on_rent_end   else "",
        "po_number":             row.po_number or "",
        "sn_request_number":     row.sn_request_number or "",
        "comments":              row.comments or "",
    })


# ─────────────────────────────────────────────
#  JUNIOR SUPER USER — WEEKLY REVIEW
# ─────────────────────────────────────────────

def _publish_readiness_for_cycle(cycle_date):
    """Return whether every active vendor has a completed response for the cycle."""
    vendor_names = list(
        VendorCompany.objects
        .filter(is_active=True)
        .values_list("name", flat=True)
    )
    audits_by_name = {
        a.vendor_name: a
        for a in VendorAudit.objects.filter(cycle_date=cycle_date)
    }

    blockers = 0
    for vendor_name in vendor_names:
        audit = audits_by_name.get(vendor_name)
        if not audit or not audit.verified:
            blockers += 1

    return blockers == 0, blockers

@login_required
def reviewer_validate_staging(request):
    """AJAX GET — validate every staging row for a given cycle week.
    Returns row-level errors so the reviewer can fix problems before publishing.
    """
    profile = _get_profile(request.user)
    if not profile or profile.role != "junior_superuser":
        return JsonResponse({"ok": False, "error": "Not authorized."}, status=403)

    try:
        week = int(request.GET.get("week", 0))
        year = int(request.GET.get("year", 0))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid week/year."}, status=400)

    staging_rows = list(RentalStaging.objects.filter(
        cycle_week=week, cycle_year=year,
    ).order_by("vendor_name", "equipment_id"))

    approved_cats = set(ApprovedEquipmentCategory.objects.values_list("name", flat=True))

    row_errors = []
    for i, row in enumerate(staging_rows, 1):
        errors = []
        if not row.equipment_id:
            errors.append("Equipment ID is empty.")
        if not row.equipment_description:
            errors.append("Description is empty.")
        if row.equipment_category and approved_cats and row.equipment_category not in approved_cats:
            errors.append(f"Category \"{row.equipment_category}\" is not in the approved list.")
        if not row.rate_daily or row.rate_daily <= 0:
            errors.append("Monthly rate must be greater than zero.")
        if not row.on_rent_start:
            errors.append("On Rent Start date is required.")
        if row.on_rent_end and row.on_rent_start and row.on_rent_end < row.on_rent_start:
            errors.append("On Rent End cannot be before On Rent Start.")
        if errors:
            row_errors.append({
                "row": i,
                "vendor": row.vendor_name,
                "equipment_id": row.equipment_id or "(empty)",
                "errors": errors,
            })

    return JsonResponse({"ok": not row_errors, "row_errors": row_errors})


@login_required
@require_POST
def reviewer_handle_delinquent(request):
    """AJAX POST — reviewer resolves a delinquent (unsubmitted) vendor by either
    carrying forward their most recent published data or excluding them entirely.

    POST body:
        vendor_name  — exact name of the vendor company
        action       — "use_previous" | "delete"
        week, year   — ISO cycle week and year
    """
    profile = _get_profile(request.user)
    if not profile or profile.role != "junior_superuser":
        return JsonResponse({"ok": False, "error": "Not authorized."}, status=403)

    vendor_name = request.POST.get("vendor_name", "").strip()
    action      = request.POST.get("action", "").strip()
    try:
        week = int(request.POST.get("week", 0))
        year = int(request.POST.get("year", 0))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid week/year."}, status=400)

    if not vendor_name or action not in ("use_previous", "delete"):
        return JsonResponse({"ok": False, "error": "Invalid parameters."}, status=400)

    try:
        cycle_date = datetime.date.fromisocalendar(year, week, 1)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Invalid cycle week/year."}, status=400)

    from django.db import transaction as _tx

    with _tx.atomic():
        # Always clear any existing (unsubmitted) staging rows for this vendor
        RentalStaging.objects.filter(vendor_name=vendor_name).filter(
            Q(cycle_week=week, cycle_year=year) | Q(cycle_week__isnull=True)
        ).delete()

        row_count = 0
        if action == "use_previous":
            # Collect the latest prior-cycle published row per equipment_id
            prior_qs = (
                RentalMaster.objects
                .filter(vendor_name=vendor_name, is_active=True)
                .exclude(cycle_week=week, cycle_year=year)
                .order_by("equipment_id", "-cycle_year", "-cycle_week")
            )
            seen: set = set()
            to_create = []
            for m in prior_qs:
                if m.equipment_id in seen:
                    continue
                seen.add(m.equipment_id)
                note = "[Carried forward from prior cycle by reviewer]"
                to_create.append(RentalStaging(
                    vendor_name=m.vendor_name,
                    vendor_code=m.vendor_code,
                    equipment_id=m.equipment_id,
                    equipment_description=m.equipment_description,
                    equipment_category=m.equipment_category,
                    quantity=m.quantity,
                    rate_daily=m.rate_daily,
                    currency=m.currency,
                    on_rent_start=m.on_rent_start,
                    on_rent_end=m.on_rent_end,
                    po_number=m.po_number,
                    sn_request_number=m.sn_request_number,
                    comments=f"{note} {m.comments}".strip() if m.comments else note,
                    cycle_week=week,
                    cycle_year=year,
                    source_file=f"carried_forward_W{week}_{year}",
                    status=SubmissionStatus.SUBMITTED,
                    submitted_by=request.user,
                    is_validated=True,
                ))
            if to_create:
                RentalStaging.objects.bulk_create(to_create)
            row_count = len(to_create)

        # Mark audit as verified so publish readiness is met
        audit, _ = VendorAudit.objects.get_or_create(
            vendor_name=vendor_name,
            cycle_date=cycle_date,
            defaults={"cadence": "weekly"},
        )
        audit.verified = True
        audit.no_change = (action == "delete")
        audit.submitted_at = timezone.now()
        audit.save(update_fields=["verified", "no_change", "submitted_at", "updated_at"])

    return JsonResponse({"ok": True, "action": action, "row_count": row_count})


@login_required
def weekly_review(request):
    user = request.user
    profile = _get_profile(user)

    if not profile or profile.role != "junior_superuser":
        return redirect("/admin/")

    # Current ISO week
    today = datetime.date.today()
    iso = today.isocalendar()
    # Allow override via ?week= and ?year= query params for testing
    try:
        current_week = int(request.GET.get("week", iso[1]))
        current_year = int(request.GET.get("year", iso[0]))
    except (ValueError, TypeError):
        current_week, current_year = iso[1], iso[0]

    # If no explicit week was requested and the default week (today) is already
    # published or has no open audit rows, look ahead up to 4 weeks to find
    # the nearest open/unpublished cycle so the reviewer lands there directly.
    if "week" not in request.GET and "year" not in request.GET:
        for lookahead in range(4):
            candidate = datetime.date.fromisocalendar(current_year, current_week, 1) + datetime.timedelta(weeks=lookahead)
            c_iso = candidate.isocalendar()
            c_week, c_year = c_iso[1], c_iso[0]
            already_pub = RentalMaster.objects.filter(cycle_week=c_week, cycle_year=c_year).exists()
            has_audits  = VendorAudit.objects.filter(cycle_date=candidate).exists()
            if not already_pub and has_audits:
                current_week, current_year = c_week, c_year
                break

    cycle_date = datetime.date.fromisocalendar(current_year, current_week, 1)

    # All active vendor companies — always show every vendor
    all_companies = VendorCompany.objects.filter(is_active=True).order_by("name")

    # Audits that exist for this cycle, keyed by vendor_name for fast lookup
    audits_by_name = {
        a.vendor_name: a
        for a in VendorAudit.objects.filter(cycle_date=cycle_date)
    }

    # Staging row counts per vendor name — scoped to the current review week,
    # submitted rows only (pending portal uploads are not yet confirmed).
    staging_count_by_name = {}
    for row in RentalStaging.objects.filter(
        vendor_name__in=[c.name for c in all_companies],
        cycle_week=current_week,
        cycle_year=current_year,
        status=SubmissionStatus.SUBMITTED,
    ).values("vendor_name").annotate(cnt=Count("id")):
        staging_count_by_name[row["vendor_name"]] = row["cnt"]

    # Build combined list — one entry per company regardless of audit existence
    audit_list = []
    submitted_count    = 0
    pending_count      = 0
    late_count         = 0
    not_required_count = 0

    for company in all_companies:
        audit = audits_by_name.get(company.name)
        row_count = staging_count_by_name.get(company.name, 0)
        if audit:
            is_not_required = (audit.cadence == "monthly" and audit.verified and audit.no_change)
            if is_not_required:
                not_required_count += 1
            elif audit.verified:
                submitted_count += 1
            elif audit.is_late:
                late_count += 1
            else:
                pending_count += 1
        else:
            pending_count += 1
        audit_list.append({
            "vendor_name": company.name,
            "audit":       audit,   # may be None if cycle not yet opened
            "row_count":   row_count,
        })

    total_vendors = len(audit_list)

    # Are monthly vendors required this cycle? True when advance_cycle created rows
    # for monthly vendors this week (i.e. it's the first full ISO week of the month).
    monthly_required = any(
        item["audit"] and item["audit"].cadence == "monthly"
        for item in audit_list
    )

    # Consolidated staging rows — only this cycle week's *submitted* rows.
    # Pending rows (vendor uploaded but not yet submitted) are excluded so that
    # data from vendors who haven't confirmed their submission doesn't appear.
    staging_rows = (
        RentalStaging.objects
        .filter(
            vendor_name__in=[c.name for c in all_companies],
            cycle_week=current_week,
            cycle_year=current_year,
            status=SubmissionStatus.SUBMITTED,
        )
        .order_by("vendor_name", "equipment_id")
    )

    # Has this week already been published to RentalMaster?
    already_published = RentalMaster.objects.filter(
        cycle_week=current_week, cycle_year=current_year
    ).exists()
    can_publish, publish_blocker_count = _publish_readiness_for_cycle(cycle_date)

    next_cycle_date = cycle_date + datetime.timedelta(days=7)
    next_iso = next_cycle_date.isocalendar()
    next_week = next_iso[1]
    next_year = next_iso[0]

    # Delinquent vendors: active vendors with no verified audit — block publish
    delinquent_vendors = [
        item["vendor_name"] for item in audit_list
        if not item["audit"] or not item["audit"].verified
    ]

    context = {
        "current_week":    current_week,
        "current_year":    current_year,
        "cycle_date":      cycle_date,
        "is_current_week": (current_week == iso[1] and current_year == iso[0]),
        "total_vendors":   total_vendors,
        "submitted_count":    submitted_count,
        "pending_count":      pending_count,
        "late_count":         late_count,
        "not_required_count": not_required_count,
        "audit_list":      audit_list,
        "delinquent_vendors": delinquent_vendors,
        "delinquent_vendors_json": json.dumps(delinquent_vendors),
        "staging_rows":    staging_rows,
        "already_published": already_published,
        "can_publish":     can_publish,
        "publish_blocker_count": publish_blocker_count,
        "next_week":       next_week,
        "next_year":       next_year,
        "equipment_categories": list(ApprovedEquipmentCategory.objects.values_list("name", flat=True)),
        "equipment_categories_json": json.dumps(list(ApprovedEquipmentCategory.objects.values_list("name", flat=True))),
        "vendor_names_json": json.dumps([c.name for c in all_companies]),
        "monthly_required": monthly_required,
    }
    return render(request, "rentals/weekly_review.html", context)


@login_required
def publish_week(request):
    """Publish all submitted staging rows for a given cycle week into RentalMaster."""
    if request.method != "POST":
        return redirect("weekly_review")

    profile = _get_profile(request.user)
    if not profile or profile.role != "junior_superuser":
        return HttpResponseForbidden("Not authorised.")

    try:
        week = int(request.POST.get("week", 0))
        year = int(request.POST.get("year", 0))
    except (ValueError, TypeError):
        messages.error(request, "Invalid week or year.")
        return redirect("weekly_review")

    try:
        cycle_date = datetime.date.fromisocalendar(year, week, 1)
    except ValueError:
        messages.error(request, "Invalid cycle week/year combination.")
        return redirect("weekly_review")

    can_publish, publish_blocker_count = _publish_readiness_for_cycle(cycle_date)

    staging_qs = RentalStaging.objects.filter(
        cycle_week=week,
        cycle_year=year,
        status=SubmissionStatus.SUBMITTED,
    )

    if not staging_qs.exists():
        messages.warning(request, f"No submitted records found for Week {week}, {year}.")
        return redirect(f"/review/?week={week}&year={year}")

    # Avoid duplicating rows already published for this week
    already_published_ids = set(
        RentalMaster.objects
        .filter(cycle_week=week, cycle_year=year)
        .values_list("approved_from_id", flat=True)
    )

    new_masters = []
    approved_staging_ids = []

    for row in staging_qs:
        if row.pk in already_published_ids:
            continue
        new_masters.append(RentalMaster(
            vendor_name=row.vendor_name,
            vendor_code=row.vendor_code,
            equipment_id=row.equipment_id,
            equipment_description=row.equipment_description,
            equipment_category=row.equipment_category,
            quantity=row.quantity,
            rate_daily=row.rate_daily,
            currency=row.currency,
            on_rent_start=row.on_rent_start,
            on_rent_end=row.on_rent_end,
            po_number=row.po_number,
            sn_request_number=row.sn_request_number,
            cycle_week=row.cycle_week,
            cycle_year=row.cycle_year,
            source_file=row.source_file,
            approved_from=row,
            approved_by=request.user,
            is_active=True,
        ))
        approved_staging_ids.append(row.pk)

    RentalMaster.objects.bulk_create(new_masters)

    # Mark staging rows as approved
    RentalStaging.objects.filter(pk__in=approved_staging_ids).update(
        status=SubmissionStatus.APPROVED,
        reviewed_by=request.user,
        reviewed_at=timezone.now(),
    )

    count = len(new_masters)
    messages.success(
        request,
        f"Week {week}, {year} published — {count} record{'s' if count != 1 else ''} moved to Master."
    )
    return redirect(f"/review/?week={week}&year={year}")


# ─────────────────────────────────────────────
#  REVIEWER — INLINE EDIT / DELETE FOR STAGING
# ─────────────────────────────────────────────

@login_required
def reviewer_inline_save(request, pk):
    """AJAX — reviewer edits a single staging row before publishing."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "errors": {"__all__": "Invalid method."}}, status=405)

    profile = _get_profile(request.user)
    if not profile or profile.role != "junior_superuser":
        return JsonResponse({"ok": False, "errors": {"__all__": "Not authorised."}}, status=403)

    try:
        row = RentalStaging.objects.get(pk=pk)
    except RentalStaging.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"__all__": "Record not found."}}, status=404)

    errors = {}
    import decimal

    vendor_name  = request.POST.get("vendor_name", row.vendor_name).strip()
    vendor_code  = request.POST.get("vendor_code", row.vendor_code or "").strip()
    eq_id        = request.POST.get("equipment_id", "").strip()
    eq_desc      = request.POST.get("equipment_description", "").strip()
    category_raw = request.POST.get("equipment_category", "").strip()
    qty_raw      = request.POST.get("quantity", "").strip()
    rate_raw     = request.POST.get("rate_daily", "").strip()
    start_raw    = request.POST.get("on_rent_start", "").strip()
    end_raw      = request.POST.get("on_rent_end", "").strip()
    po           = request.POST.get("po_number", row.po_number or "").strip()
    sn           = request.POST.get("sn_request_number", row.sn_request_number or "").strip()
    comments     = request.POST.get("comments", row.comments or "").strip()

    active_vendors = list(VendorCompany.objects.filter(is_active=True).values_list("name", flat=True))
    if not vendor_name:
        errors["vendor_name"] = "Vendor is required."
    elif vendor_name not in active_vendors:
        errors["vendor_name"] = f'"{vendor_name}" is not an active vendor.'

    if not eq_id:
        errors["equipment_id"] = "Equipment ID is required."
    if not eq_desc:
        errors["equipment_description"] = "Description is required."

    approved_cats = list(ApprovedEquipmentCategory.objects.values_list("name", flat=True))
    if not category_raw:
        errors["equipment_category"] = "Category is required — select from the dropdown."
    elif approved_cats and category_raw not in approved_cats:
        errors["equipment_category"] = f'"{category_raw}" is not an approved category.'

    qty = None
    try:
        qty = int(qty_raw)
        if qty < 1:
            errors["quantity"] = "Quantity must be at least 1."
    except (ValueError, TypeError):
        errors["quantity"] = "Enter a valid whole number."

    rate = None
    try:
        rate = decimal.Decimal(rate_raw.replace(",", "").lstrip("$"))
        if rate <= 0:
            errors["rate_daily"] = "Rate must be greater than zero."
    except (decimal.InvalidOperation, ValueError):
        errors["rate_daily"] = "Enter a valid dollar amount."

    start_date = None
    try:
        start_date = datetime.date.fromisoformat(start_raw)
    except (ValueError, TypeError):
        errors["on_rent_start"] = "Enter a valid date (YYYY-MM-DD)."

    end_date = None
    if end_raw:
        try:
            end_date = datetime.date.fromisoformat(end_raw)
            if start_date and end_date < start_date:
                errors["on_rent_end"] = "End date cannot be before start date."
        except (ValueError, TypeError):
            errors["on_rent_end"] = "Enter a valid date (YYYY-MM-DD)."

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    row.vendor_name           = vendor_name
    row.vendor_code           = vendor_code or row.vendor_code
    row.equipment_id          = eq_id
    row.equipment_description = eq_desc
    row.equipment_category    = category_raw
    row.quantity              = qty
    row.rate_daily            = rate
    row.on_rent_start         = start_date
    row.on_rent_end           = end_date
    row.po_number             = po or row.po_number
    row.sn_request_number     = sn or row.sn_request_number
    row.comments              = comments
    row.save()

    return JsonResponse({
        "ok":                    True,
        "vendor_name":           row.vendor_name,
        "vendor_code":           row.vendor_code or "",
        "equipment_id":          row.equipment_id,
        "equipment_description": row.equipment_description,
        "equipment_category":    row.equipment_category or "",
        "quantity":              row.quantity,
        "rate_daily":            str(row.rate_daily),
        "on_rent_start":         row.on_rent_start.isoformat() if row.on_rent_start else "",
        "on_rent_end":           row.on_rent_end.isoformat()   if row.on_rent_end   else "",
        "po_number":             row.po_number or "",
        "sn_request_number":     row.sn_request_number or "",
        "comments":              row.comments or "",
    })


@login_required
def reviewer_delete_row(request, pk):
    """AJAX — reviewer removes a staging row before publishing."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "errors": {"__all__": "Invalid method."}}, status=405)

    profile = _get_profile(request.user)
    if not profile or profile.role != "junior_superuser":
        return JsonResponse({"ok": False, "errors": {"__all__": "Not authorised."}}, status=403)

    try:
        row = RentalStaging.objects.get(pk=pk)
    except RentalStaging.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"__all__": "Record not found."}}, status=404)

    row.delete()
    return JsonResponse({"ok": True})
