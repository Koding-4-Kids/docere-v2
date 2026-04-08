"""Generate Docere NDA PDF and send via Resend."""

import os
import sys
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ── Brand colors (matches equity grants) ──
ORANGE = HexColor("#F15524")
ORANGE_LIGHT = HexColor("#FDE8E0")
DARK = HexColor("#1A1A1A")
GRAY = HexColor("#666666")
LIGHT_GRAY = HexColor("#999999")
BORDER = HexColor("#E5E5E0")
BG_LIGHT = HexColor("#FAFAF7")

LOGO_PATH = "/Users/asfawy/docere-v2/frontend/public/docere-logo.png"
OUTPUT_DIR = "/Users/asfawy/docere-v2/nda-agreements"


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "DocTitle", parent=styles["Title"], fontSize=28, textColor=DARK,
        spaceAfter=6, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "Subtitle", parent=styles["Normal"], fontSize=14, textColor=ORANGE,
        spaceAfter=12, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "SectionHead", parent=styles["Normal"], fontSize=16, textColor=ORANGE,
        spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "BodyText2", parent=styles["Normal"], fontSize=11, textColor=DARK,
        spaceAfter=6, fontName="Helvetica", leading=16,
    ))
    styles.add(ParagraphStyle(
        "SmallGray", parent=styles["Normal"], fontSize=9, textColor=LIGHT_GRAY,
        spaceAfter=4, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "BulletItem", parent=styles["Normal"], fontSize=10, textColor=DARK,
        fontName="Helvetica", leftIndent=20, spaceAfter=3, leading=14,
        bulletFontName="Helvetica", bulletFontSize=10, bulletColor=ORANGE,
    ))
    styles.add(ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=8, textColor=LIGHT_GRAY,
        fontName="Helvetica", alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "ClauseNum", parent=styles["Normal"], fontSize=11, textColor=ORANGE,
        fontName="Helvetica-Bold", leading=16,
    ))
    styles.add(ParagraphStyle(
        "ClauseBody", parent=styles["Normal"], fontSize=10, textColor=DARK,
        fontName="Helvetica", leading=15, leftIndent=24, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        "HighlightBox", parent=styles["Normal"], fontSize=12, textColor=DARK,
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=18,
    ))
    return styles


def generate_nda(name, role="Software Engineering Intern", effective_date="March 17, 2026"):
    styles = build_styles()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = name.replace(" ", "_")
    filepath = os.path.join(OUTPUT_DIR, f"Docere_NDA_{safe_name}.pdf")

    doc = SimpleDocTemplate(
        filepath, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )

    story = []

    # ── Logo ──
    logo = Image(LOGO_PATH, width=1.8 * inch, height=0.45 * inch)
    logo.hAlign = "LEFT"
    story.append(logo)
    story.append(Spacer(1, 8))

    # ── Divider ──
    story.append(HRFlowable(width="100%", thickness=2, color=ORANGE, spaceAfter=12))

    # ── Title ──
    story.append(Paragraph("Non-Disclosure Agreement", styles["DocTitle"]))
    story.append(Paragraph(f"Issued to {name}", styles["Subtitle"]))
    story.append(Paragraph(
        f"{effective_date}  |  Koding-4-Kids, Inc. (d/b/a Docere)",
        styles["SmallGray"],
    ))
    story.append(Spacer(1, 16))

    # ── Highlight box ──
    box_data = [
        [Paragraph("CONFIDENTIAL", styles["HighlightBox"])],
        [Spacer(1, 4)],
        [Paragraph(f"{role}", styles["HighlightBox"])],
    ]
    box_table = Table(box_data, colWidths=[5 * inch], rowHeights=[28, 6, 24])
    box_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ORANGE_LIGHT),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (0, 0), 14),
        ("BOTTOMPADDING", (0, -1), (0, -1), 12),
        ("BOX", (0, 0), (-1, -1), 1.5, ORANGE),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    box_table.hAlign = "CENTER"
    story.append(box_table)
    story.append(Spacer(1, 20))

    # ── Parties ──
    story.append(Paragraph("Parties", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))

    parties_data = [
        ["Disclosing Party", "Koding-4-Kids, Inc. (d/b/a Docere)"],
        ["Receiving Party", f"{name} ({role})"],
        ["Effective Date", effective_date],
    ]
    parties_table = Table(parties_data, colWidths=[2.2 * inch, 4.5 * inch])
    parties_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), ORANGE_LIGHT),
        ("TEXTCOLOR", (0, 0), (0, -1), DARK),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 1, BORDER),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, BORDER),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 14))

    # ── Recitals ──
    story.append(Paragraph("Recitals", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph(
        f"WHEREAS, <b>Koding-4-Kids, Inc.</b> (d/b/a <b>Docere</b>) (the \"Company\") is engaged in the "
        "development of educational technology software and related services; and",
        styles["BodyText2"],
    ))
    story.append(Paragraph(
        f"WHEREAS, <b>{name}</b> (the \"Receiving Party\") will be serving as a {role} "
        "and will have access to confidential and proprietary information of the Company; and",
        styles["BodyText2"],
    ))
    story.append(Paragraph(
        "WHEREAS, the Company desires to protect its confidential information and trade secrets;",
        styles["BodyText2"],
    ))
    story.append(Paragraph(
        "NOW, THEREFORE, in consideration of the mutual promises and covenants contained herein, "
        "and for other good and valuable consideration, the receipt and sufficiency of which are "
        "hereby acknowledged, the parties agree as follows:",
        styles["BodyText2"],
    ))
    story.append(Spacer(1, 10))

    # ── Clauses ──
    clauses = [
        (
            "1. Definition of Confidential Information",
            "\"Confidential Information\" means any and all non-public information disclosed by the Company "
            "to the Receiving Party, whether orally, in writing, electronically, or by any other means, "
            "including but not limited to: (a) source code, algorithms, software architecture, and technical "
            "designs; (b) product roadmaps, feature plans, and development strategies; (c) business plans, "
            "financial data, pricing models, and revenue projections; (d) user data, analytics, and usage "
            "patterns; (e) intellectual property, inventions, and trade secrets; (f) information about "
            "partnerships, investors, and business relationships; (g) any information marked or designated "
            "as confidential; and (h) any information that a reasonable person would understand to be "
            "confidential given the nature of the information and circumstances of disclosure."
        ),
        (
            "2. Obligations of the Receiving Party",
            "The Receiving Party agrees to: (a) hold all Confidential Information in strict confidence; "
            "(b) not disclose any Confidential Information to any third party without the prior written "
            "consent of the Company; (c) use Confidential Information solely for the purpose of performing "
            "duties as a {role} for the Company; (d) take all reasonable precautions to prevent unauthorized "
            "disclosure or use of Confidential Information, using at least the same degree of care used to "
            "protect their own confidential information, but in no event less than reasonable care; and "
            "(e) promptly notify the Company of any unauthorized disclosure or use of Confidential Information.".format(role=role)
        ),
        (
            "3. Exclusions",
            "Confidential Information does not include information that: (a) is or becomes publicly available "
            "through no fault of the Receiving Party; (b) was rightfully known to the Receiving Party prior "
            "to disclosure by the Company, as evidenced by written records; (c) is independently developed by "
            "the Receiving Party without use of or reference to the Confidential Information; or (d) is "
            "rightfully received from a third party without restriction on disclosure."
        ),
        (
            "4. Intellectual Property",
            "All Confidential Information remains the exclusive property of the Company. Nothing in this "
            "Agreement grants the Receiving Party any rights, title, or interest in the Confidential "
            "Information or any intellectual property of the Company. Any work product, inventions, or "
            "developments created by the Receiving Party during their engagement that relate to the "
            "Company's business or that result from the use of Confidential Information shall be the "
            "sole property of the Company."
        ),
        (
            "5. Return of Materials",
            "Upon termination of the Receiving Party's engagement with the Company, or upon the Company's "
            "written request, the Receiving Party shall promptly: (a) return all documents, files, and "
            "other materials containing Confidential Information; (b) delete all electronic copies of "
            "Confidential Information from personal devices and accounts; and (c) certify in writing "
            "that all Confidential Information has been returned or destroyed."
        ),
        (
            "6. Term and Duration",
            "This Agreement is effective as of the Effective Date and the confidentiality obligations "
            "shall survive for a period of two (2) years following the termination of the Receiving "
            "Party's engagement with the Company, or for as long as the Confidential Information "
            "remains a trade secret, whichever is longer."
        ),
        (
            "7. Remedies",
            "The Receiving Party acknowledges that any breach of this Agreement may cause irreparable harm "
            "to the Company for which monetary damages alone would be inadequate. Accordingly, the Company "
            "shall be entitled to seek equitable relief, including injunction and specific performance, in "
            "addition to all other remedies available at law or in equity."
        ),
        (
            "8. Governing Law",
            "This Agreement shall be governed by and construed in accordance with the laws of the State "
            "of Maryland, without regard to its conflict of laws principles."
        ),
        (
            "9. Entire Agreement",
            "This Agreement constitutes the entire agreement between the parties with respect to the "
            "subject matter hereof and supersedes all prior and contemporaneous understandings, agreements, "
            "representations, and warranties, both written and oral, with respect to such subject matter."
        ),
    ]

    story.append(Paragraph("Terms and Conditions", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))

    for title, body in clauses:
        story.append(Paragraph(title, styles["ClauseNum"]))
        story.append(Paragraph(body, styles["ClauseBody"]))

    story.append(Spacer(1, 24))

    # ── Signature Block ──
    story.append(HRFlowable(width="100%", thickness=1, color=ORANGE, spaceAfter=14))
    sig_data = [
        [
            Paragraph("Receiving Party", styles["SmallGray"]),
            Paragraph("Disclosing Party", styles["SmallGray"]),
        ],
        [Spacer(1, 30), Spacer(1, 30)],
        [
            Paragraph("_" * 40, styles["BodyText2"]),
            Paragraph("_" * 40, styles["BodyText2"]),
        ],
        [
            Paragraph(name, styles["BodyText2"]),
            Paragraph("Youdahe Asfaw, Co-Founder", styles["BodyText2"]),
        ],
        [
            Paragraph(f"{role}", styles["SmallGray"]),
            Paragraph("Koding-4-Kids, Inc. (d/b/a Docere)", styles["SmallGray"]),
        ],
        [Spacer(1, 8), Spacer(1, 8)],
        [
            Paragraph("Date: _______________", styles["SmallGray"]),
            Paragraph(f"Date: {effective_date}", styles["SmallGray"]),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[3.3 * inch, 3.3 * inch])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 20))

    # ── Footer ──
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
    story.append(Paragraph(
        "This document is issued by Koding-4-Kids, Inc. (d/b/a Docere). "
        "This NDA should be reviewed by legal counsel before execution. "
        "By signing, both parties acknowledge they have read, understood, and agree to be bound by the terms herein.",
        styles["Footer"],
    ))

    doc.build(story)
    print(f"  Generated: {filepath}")
    return filepath


def send_nda_email(filepath, recipient_email, intern_name, role, api_key, from_email="nda@docere.ai"):
    """Send NDA PDF via Resend API."""
    import resend
    resend.api_key = api_key

    with open(filepath, "rb") as f:
        pdf_bytes = f.read()

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    params = {
        "from": from_email,
        "to": [recipient_email],
        "subject": f"Docere — Non-Disclosure Agreement for {intern_name}",
        "html": f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="padding: 24px 0; border-bottom: 2px solid #F15524;">
                <img src="https://raw.githubusercontent.com/Koding-4-Kids/docere-v2/main/frontend/public/docere-logo.png"
                     alt="Docere" style="height: 36px;" />
            </div>
            <div style="padding: 24px 0;">
                <h2 style="color: #1A1A1A; margin: 0 0 8px 0;">Non-Disclosure Agreement</h2>
                <p style="color: #666; font-size: 15px; line-height: 1.6;">
                    Hi Youdahe,
                </p>
                <p style="color: #666; font-size: 15px; line-height: 1.6;">
                    Attached is the <b>Non-Disclosure Agreement</b> for
                    <span style="color: #F15524; font-weight: bold;">{intern_name}</span>,
                    who will be joining as a <b>{role}</b>.
                </p>
                <p style="color: #666; font-size: 15px; line-height: 1.6;">
                    Please review and have both parties sign the agreement before {intern_name}'s start date.
                </p>
                <p style="color: #1A1A1A; font-size: 15px; margin-top: 24px;">
                    — Docere Automated Documents<br/>
                    <span style="color: #999; font-size: 13px;">Koding-4-Kids, Inc.</span>
                </p>
            </div>
            <div style="padding: 16px 0; border-top: 1px solid #E5E5E0;">
                <p style="color: #999; font-size: 11px; margin: 0;">
                    This is an automated email from Docere (Koding-4-Kids, Inc.).
                </p>
            </div>
        </div>
        """,
        "attachments": [
            {
                "filename": f"Docere_NDA_{intern_name.replace(' ', '_')}.pdf",
                "content": pdf_b64,
                "type": "application/pdf",
            }
        ],
    }

    try:
        email = resend.Emails.send(params)
        print(f"  SENT to {recipient_email} — ID: {email.get('id', 'ok')}")
    except Exception as e:
        print(f"  FAILED: {e}")


if __name__ == "__main__":
    INTERN_NAME = "Krish Suryavanshi"
    INTERN_ROLE = "Software Engineering Intern"
    EFFECTIVE_DATE = "April 17, 2026"
    SEND_TO = "youdaheasfaw@gmail.com"

    print("=" * 60)
    print("Generating Docere NDA")
    print("=" * 60)
    print()
    print(f"  Intern:    {INTERN_NAME}")
    print(f"  Role:      {INTERN_ROLE}")
    print(f"  Date:      {EFFECTIVE_DATE}")
    print(f"  Send to:   {SEND_TO}")
    print()

    filepath = generate_nda(INTERN_NAME, INTERN_ROLE, EFFECTIVE_DATE)

    print()

    if len(sys.argv) > 1 and sys.argv[1] == "--send":
        api_key = os.environ.get("RESEND_API_KEY")
        from_email = os.environ.get("RESEND_FROM", "nda@docere.ai")
        if not api_key:
            print("ERROR: Set RESEND_API_KEY environment variable")
            sys.exit(1)
        print("Sending NDA via Resend...")
        send_nda_email(filepath, SEND_TO, INTERN_NAME, INTERN_ROLE, api_key, from_email)
    else:
        print(f"PDF saved to: {filepath}")
        print()
        print("To send via email, run:")
        print("  RESEND_API_KEY=re_xxx python generate_nda_pdf.py --send")
