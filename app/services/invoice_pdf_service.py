"""Genera el PDF de factura para un PlatformCharge (cobro del dueno de la
plataforma hacia una clinica). Layout inspirado en el ejemplo que el
usuario compartio (estilo Wave: banda oscura "INVOICE" + monto adeudado,
BILL TO, tabla de items, total, linea de pago). Usa reportlab (puro
Python, sin dependencias nativas -- WeasyPrint/wkhtmltopdf requieren
Cairo/Pango o un binario externo, dolorosos de instalar en Windows)."""

from datetime import datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

from app.models.platform_billing import ChargeStatus, PlatformCharge

ISSUER_NAME = "Salvio"

DARK = colors.HexColor("#3f3f3f")
GREY = colors.HexColor("#757575")
LIGHT_GREY = colors.HexColor("#f2f2f2")
INK = colors.HexColor("#1a1a1a")


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def generate_invoice_pdf(charge: PlatformCharge, tenant_name: str, billing_contact_name: str | None, billing_contact_phone: str | None) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0,
        bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle("label", parent=styles["Normal"], fontSize=8, textColor=GREY, spaceAfter=2)
    value_style = ParagraphStyle("value", parent=styles["Normal"], fontSize=10, textColor=INK)
    value_bold = ParagraphStyle("valueBold", parent=value_style, fontName="Helvetica-Bold")
    right_value = ParagraphStyle("rightValue", parent=value_style, alignment=TA_RIGHT)
    right_label = ParagraphStyle("rightLabel", parent=label_style, alignment=TA_RIGHT)

    amount_due = Decimal("0.00") if charge.status in (ChargeStatus.paid, ChargeStatus.void) else charge.amount

    elements = []

    # --- Banda superior: INVOICE + Amount Due ------------------------------
    header_table = Table(
        [
            [
                Paragraph("<font size=22 color='white'><b>INVOICE</b></font>", styles["Normal"]),
                Paragraph(
                    f"<font size=9 color='white'>Amount Due (USD)</font><br/><font size=20 color='white'><b>{_money(amount_due)}</b></font>",
                    ParagraphStyle("amountHeader", parent=styles["Normal"], alignment=TA_RIGHT, leading=24),
                ),
            ]
        ],
        colWidths=[4.1 * inch, 3.3 * inch],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), DARK),
                ("BACKGROUND", (1, 0), (1, 0), GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 24),
                ("RIGHTPADDING", (1, 0), (1, 0), 24),
                ("TOPPADDING", (0, 0), (-1, -1), 28),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 28),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 0.35 * inch))

    # --- BILL TO + metadata de la factura -----------------------------------
    bill_to_lines = [Paragraph("BILL TO", label_style), Paragraph(f"<b>{tenant_name}</b>", value_bold)]
    if billing_contact_name:
        bill_to_lines.append(Paragraph(billing_contact_name, value_style))
    if billing_contact_phone:
        bill_to_lines.append(Paragraph(billing_contact_phone, value_style))
    bill_to_cell = bill_to_lines

    meta_rows = [
        ["Invoice Number:", str(charge.invoice_number)],
        ["Invoice Date:", charge.created_at.strftime("%B %d, %Y")],
        ["Payment Due:", charge.due_date.strftime("%B %d, %Y") if charge.due_date else "-"],
        ["Amount Due (USD):", _money(amount_due)],
    ]
    meta_table = Table(meta_rows, colWidths=[1.6 * inch, 1.7 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, -1), (1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    top_info = Table([[bill_to_cell, meta_table]], colWidths=[4.1 * inch, 3.3 * inch])
    top_info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(top_info)
    elements.append(Spacer(1, 0.3 * inch))

    # --- Tabla de items ------------------------------------------------------
    description = Paragraph(f"<b>{charge.period_label}</b>" + (f"<br/><font size=8 color='#757575'>{charge.notes}</font>" if charge.notes else ""), value_style)
    items_header = ["ITEMS", "QUANTITY", "PRICE", "AMOUNT"]
    items_rows = [items_header, [description, "1", _money(charge.amount), _money(charge.amount)]]
    items_table = Table(items_rows, colWidths=[3.4 * inch, 1.1 * inch, 1.4 * inch, 1.5 * inch])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, 0), GREY),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#dddddd")),
                ("BACKGROUND", (0, 1), (-1, 1), LIGHT_GREY),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (0, -1), 10),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 0.15 * inch))

    # --- Total / pago ----------------------------------------------------------
    totals_rows = [["Total:", _money(charge.amount)]]
    if charge.status == ChargeStatus.paid and charge.paid_at:
        totals_rows.append([f"Payment on {charge.paid_at.strftime('%B %d, %Y')}:", _money(charge.amount)])
    elif charge.status == ChargeStatus.void:
        totals_rows.append(["Cobro anulado:", "-"])
    totals_rows.append(["Amount Due (USD):", _money(amount_due)])

    totals_table = Table(totals_rows, colWidths=[2.6 * inch, 1.5 * inch], hAlign="RIGHT")
    totals_style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#dddddd")),
    ]
    totals_table.setStyle(TableStyle(totals_style))
    elements.append(totals_table)
    elements.append(Spacer(1, 0.9 * inch))

    # --- Footer: emisor ----------------------------------------------------
    elements.append(Table([[Paragraph("", value_style)]], colWidths=[6.8 * inch], style=[("LINEABOVE", (0, 0), (-1, 0), 0.75, colors.HexColor("#dddddd"))]))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(f"<b>{ISSUER_NAME}</b>", value_bold))

    doc.build(elements)
    return buffer.getvalue()
