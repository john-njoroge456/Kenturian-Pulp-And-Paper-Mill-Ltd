from datetime import date, timedelta
from io import BytesIO

from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import OrderItem, OrderRequest

NAVY = "14335C"

ORDER_COLUMNS = [
    # (header, width)
    ("Reference", 13), ("Order date", 17), ("Company", 26), ("Contact person", 20),
    ("Phone", 16), ("Email", 26), ("Item #", 7), ("Item", 22), ("Colour", 14),
    ("Length (mm)", 12), ("GSM", 7), ("Quantity (kg)", 13), ("Status", 11),
    ("Preferred delivery", 17), ("Delivery location",
                                 22), ("LPO attached", 12), ("Notes", 40),
]


def _style_header(ws, columns):
    fill = PatternFill("solid", start_color=NAVY)
    for col, (title, width) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A2"


def orders_workbook(orders):
    """One row per item, so staff can sort, filter and pivot in Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Order items"
    _style_header(ws, ORDER_COLUMNS)

    row = 1
    for order in orders.prefetch_related("items").order_by("-created_at"):
        created = timezone.localtime(order.created_at).replace(tzinfo=None)
        for item in order.items.all():
            ws.append([
                order.reference, created, order.company_name, order.contact_person,
                order.phone, order.email, item.position, item.item_description,
                item.color, float(item.length), item.gsm, item.quantity,
                order.get_status_display(), order.preferred_delivery_date,
                order.delivery_location, "Yes" if order.lpo_file else "No", order.notes,
            ])
            row += 1

    for r in range(2, row + 1):
        ws.cell(row=r, column=2).number_format = "dd mmm yyyy hh:mm"
        ws.cell(row=r, column=12).number_format = "#,##0"
        ws.cell(row=r, column=14).number_format = "dd mmm yyyy"
        ws.cell(row=r, column=17).alignment = Alignment(
            wrap_text=True, vertical="top")

    if row > 1:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(ORDER_COLUMNS))}{row}"
        total_row = row + 2
        ws.cell(row=total_row, column=11, value="Total").font = Font(bold=True)
        total = ws.cell(row=total_row, column=12, value=f"=SUM(L2:L{row})")
        total.font = Font(bold=True)
        total.number_format = "#,##0"
    return wb


def xlsx_response(wb, filename):
    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

# ---------------------------------------------------------------------------
# Order report (admin "Order report" page)
# ---------------------------------------------------------------------------


PRESETS = [
    ("this_month", "This month"),
    ("last_month", "Last month"),
    ("last_30", "Last 30 days"),
    ("this_year", "This year"),
]


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def resolve_period(params):
    """Work out the report dates from ?preset= or ?start=&end=."""
    today = timezone.localdate()
    start, end = _parse_date(params.get(
        "start")), _parse_date(params.get("end"))
    if start and end:
        if start > end:
            start, end = end, start
        return "custom", start, end

    preset = params.get("preset") or "this_month"
    if preset == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif preset == "last_30":
        start, end = today - timedelta(days=29), today
    elif preset == "this_year":
        start, end = today.replace(month=1, day=1), today
    else:
        preset = "this_month"
        start, end = today.replace(day=1), today
    return preset, start, end


def _change(current, previous):
    if not previous:
        return None
    return round((current - previous) * 100 / previous)


def build_order_report(start, end):
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    orders = OrderRequest.objects.filter(
        created_at__date__gte=start, created_at__date__lte=end)
    prev_orders = OrderRequest.objects.filter(
        created_at__date__gte=prev_start, created_at__date__lte=prev_end)
    items = OrderItem.objects.filter(order__in=orders.values("pk"))
    prev_items = OrderItem.objects.filter(order__in=prev_orders.values("pk"))

    order_count = orders.count()
    total_kg = items.aggregate(t=Sum("quantity"))["t"] or 0
    lines = items.count()
    prev_count = prev_orders.count()
    prev_kg = prev_items.aggregate(t=Sum("quantity"))["t"] or 0

    def with_share(rows):
        for r in rows:
            r["share"] = round(r["kg"] * 100 / total_kg) if total_kg else 0
        return rows

    by_product = with_share(list(
        items.values("item_description")
        .annotate(kg=Sum("quantity"), lines=Count("id"), orders=Count("order", distinct=True))
        .order_by("-kg")))

    by_colour = with_share(list(
        items.values("color")
        .annotate(kg=Sum("quantity"), lines=Count("id"))
        .order_by("-kg")))

    status_counts = {r["status"]: r["n"]
                     for r in orders.values("status").annotate(n=Count("id"))}
    status_kg = {r["order__status"]: r["kg"] for r in
                 items.values("order__status").annotate(kg=Sum("quantity"))}
    by_status = [
        {
            "code": code,
            "label": label,
            "orders": status_counts.get(code, 0),
            "kg": status_kg.get(code) or 0,
            "share": round(status_counts.get(code, 0) * 100 / order_count) if order_count else 0,
        }
        for code, label in OrderRequest.STATUS_CHOICES
    ]

    top_clients = with_share(list(
        items.values("order__company_name")
        .annotate(kg=Sum("quantity"), orders=Count("order", distinct=True))
        .order_by("-kg")[:10]))

    stale_new = OrderRequest.objects.filter(
        status="new", created_at__lt=timezone.now() - timedelta(days=2)).count()

    return {
        "start": start, "end": end, "days": days,
        "prev_start": prev_start, "prev_end": prev_end,
        "orders": orders,
        "order_count": order_count, "total_kg": total_kg, "lines": lines,
        "avg_kg": round(total_kg / order_count) if order_count else 0,
        "prev_count": prev_count, "prev_kg": prev_kg,
        "count_change": _change(order_count, prev_count),
        "kg_change": _change(total_kg, prev_kg),
        "by_product": by_product, "by_colour": by_colour,
        "by_status": by_status, "top_clients": top_clients,
        "stale_new": stale_new,
    }


def _table_sheet(wb, title, columns, rows):
    ws = wb.create_sheet(title)
    _style_header(ws, columns)
    for row in rows:
        ws.append(row)
    for r in range(2, len(rows) + 2):
        for c in range(1, len(columns) + 1):
            if isinstance(ws.cell(row=r, column=c).value, int):
                ws.cell(row=r, column=c).number_format = "#,##0"
    return ws


def report_workbook(report):
    wb = orders_workbook(report["orders"])   # "Order items" sheet

    summary = wb.create_sheet("Summary", 0)
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 18
    summary.column_dimensions["C"].width = 18
    summary["A1"] = "Kenturian Pulp & Paper Mills — Order report"
    summary["A1"].font = Font(bold=True, size=14, color=NAVY)
    summary["A2"] = f"{report['start']:%d %b %Y} to {report['end']:%d %b %Y}"
    summary.append([])
    summary.append(["", "This period", "Previous period"])
    for cell in summary[4]:
        cell.font = Font(bold=True)
    summary.append(["Orders", report["order_count"], report["prev_count"]])
    summary.append(
        ["Total quantity (kg)", report["total_kg"], report["prev_kg"]])
    summary.append(["Item lines", report["lines"], ""])
    summary.append(["Average kg per order", report["avg_kg"], ""])
    for r in range(5, 9):
        for c in (2, 3):
            summary.cell(row=r, column=c).number_format = "#,##0"

    _table_sheet(wb, "By product",
                 [("Item", 26), ("Quantity (kg)", 14),
                  ("Share %", 9), ("Item lines", 11), ("Orders", 9)],
                 [[r["item_description"], r["kg"], r["share"], r["lines"], r["orders"]] for r in report["by_product"]])
    _table_sheet(wb, "By colour",
                 [("Colour", 20), ("Quantity (kg)", 14),
                  ("Share %", 9), ("Item lines", 11)],
                 [[r["color"] or "—", r["kg"], r["share"], r["lines"]] for r in report["by_colour"]])
    _table_sheet(wb, "By status",
                 [("Status", 14), ("Orders", 9), ("Quantity (kg)", 14)],
                 [[r["label"], r["orders"], r["kg"]] for r in report["by_status"]])
    _table_sheet(wb, "Top clients",
                 [("Company", 30), ("Quantity (kg)", 14),
                  ("Share %", 9), ("Orders", 9)],
                 [[r["order__company_name"], r["kg"], r["share"], r["orders"]] for r in report["top_clients"]])
    return wb
