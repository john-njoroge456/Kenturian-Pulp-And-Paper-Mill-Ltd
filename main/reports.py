from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

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
