"""Generate individual Docere contributor equity grant PDFs and send via Resend."""

import os
import sys
import json
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ── Brand colors ──
ORANGE = HexColor("#F15524")
ORANGE_LIGHT = HexColor("#FDE8E0")
DARK = HexColor("#1A1A1A")
GRAY = HexColor("#666666")
LIGHT_GRAY = HexColor("#999999")
BORDER = HexColor("#E5E5E0")
BG_LIGHT = HexColor("#FAFAF7")

LOGO_PATH = "/Users/asfawy/docere-v2/frontend/public/docere-logo.png"
OUTPUT_DIR = "/Users/asfawy/docere-v2/equity-grants"

# ── Equity formula ──
# Base: 3.00% for each founding team member
# Bonuses: +0.05% per commit, +0.10% per merged PR, +0.05% per opened PR,
#          +0.05% per issue, +0.03% per comment, +0.10% per extra repo
BASE_EQUITY = 3.00
BONUS_PER_COMMIT = 0.05
BONUS_PER_PR_MERGED = 0.10
BONUS_PER_PR_OPENED = 0.05
BONUS_PER_ISSUE = 0.05
BONUS_PER_COMMENT = 0.03
BONUS_PER_EXTRA_REPO = 0.10


def calc_equity(data):
    bonus = (
        data["commits"] * BONUS_PER_COMMIT
        + data["prs_merged"] * BONUS_PER_PR_MERGED
        + data["prs_opened"] * BONUS_PER_PR_OPENED
        + data["issues_opened"] * BONUS_PER_ISSUE
        + data["issue_comments"] * BONUS_PER_COMMENT
        + max(0, len(data["repos"]) - 1) * BONUS_PER_EXTRA_REPO
    )
    return round(BASE_EQUITY + bonus, 2)


# ── Contributor data ──
CONTRIBUTORS = {
    "kevinthai256": {
        "name": "Kevin Thai",
        "email": None,
        "github": "kevinthai256",
        "commits": 19,
        "repos": ["backend1", "lesson-page"],
        "prs_opened": 2,
        "prs_merged": 1,
        "issues_opened": 1,
        "issue_comments": 8,
        "pr_reviews": 0,
        "primary_work": "Cookie consent & GDPR compliance, responsive design, privacy/cookie policy pages, lesson page scrolling, lazy loading, lock file management",
        "key_commits": [
            "Ensure consistent modification of cookie preferences",
            "Added public access routes for privacy and cookie policies",
            "Added Cookie Policy page and functional checkboxes",
            "Added mobile adaptive cookie consent banner",
            "Revised scrolling behavior (lesson-page)",
        ],
        "contribution_period": "Jan 6, 2026 – Jan 17, 2026",
    },
    "JoshuaEkoja": {
        "name": "Joshua Ekoja",
        "email": None,
        "github": "JoshuaEkoja",
        "commits": 6,
        "repos": ["Blossom-Chat-bot"],
        "prs_opened": 0,
        "prs_merged": 0,
        "issues_opened": 0,
        "issue_comments": 0,
        "pr_reviews": 0,
        "primary_work": "Built initial Blossom onboarding chatbot prototype from scratch",
        "key_commits": [
            "Initial commit of Blossom chatbot project",
            "Completed chatbot implementation",
        ],
        "contribution_period": "Aug 4, 2025 – Aug 5, 2025",
    },
    "jayvionthaing": {
        "name": "Jayviont Haing",
        "email": None,
        "github": "jayvionthaing",
        "commits": 4,
        "repos": ["backend1"],
        "prs_opened": 1,
        "prs_merged": 1,
        "issues_opened": 0,
        "issue_comments": 0,
        "pr_reviews": 0,
        "primary_work": "Bundle size optimization, code splitting, performance improvements, bundle visualization",
        "key_commits": [
            "Bundle Size Optimization and Performance Improvements (Issue #44)",
            "Add bundle visualizer and implement code splitting",
        ],
        "contribution_period": "Jan 12, 2026 – Jan 20, 2026",
    },
    "Cjackett13": {
        "name": "CJ Ackett",
        "email": None,
        "github": "Cjackett13",
        "commits": 3,
        "repos": ["backend1"],
        "prs_opened": 6,
        "prs_merged": 5,
        "issues_opened": 0,
        "issue_comments": 0,
        "pr_reviews": 0,
        "primary_work": "Terms of Service implementation, Privacy Policy links, email notification for ToS acceptance",
        "key_commits": [
            "Terms of service email notification",
            "Add Terms of Service and Privacy Policy links to Login page",
            "Terms of service page implementation",
        ],
        "contribution_period": "Jan 14, 2026 – Jan 15, 2026",
    },
    "Lukietoo": {
        "name": "Luke",
        "email": None,
        "github": "Lukietoo",
        "commits": 0,
        "repos": ["backend1"],
        "prs_opened": 1,
        "prs_merged": 0,
        "issues_opened": 0,
        "issue_comments": 0,
        "pr_reviews": 0,
        "primary_work": "CSRF protection implementation and backend security work",
        "key_commits": [
            "PR #49: Backend CSRF protection implemented and verified",
        ],
        "contribution_period": "Jan 2026",
    },
    "okosei04": {
        "name": "Kofi Osei",
        "email": None,
        "github": "okosei04",
        "commits": 11,
        "repos": ["backend1"],
        "prs_opened": 4,
        "prs_merged": 3,
        "issues_opened": 0,
        "issue_comments": 0,
        "pr_reviews": 0,
        "primary_work": "Initial backend API setup, authentication fixes, database security improvements, purchase limiter fix, issue #48 resolution",
        "key_commits": [
            "Initial commit: Koding 4 Kids Backend API — complete educational platform with authentication, lessons, chatbot, and admin features",
            "Improvement to database security",
            "Authentication fix",
            "Issue #48 suggested fix with fix for issue #7",
            "Purchase limiter fix",
        ],
        "contribution_period": "Jun 24, 2025 – Jan 15, 2026",
    },
    "NoMo-101": {
        "name": "Noah Moore",
        "email": None,
        "github": "NoMo-101",
        "commits": 0,
        "repos": ["backend1"],
        "prs_opened": 0,
        "prs_merged": 0,
        "issues_opened": 0,
        "issue_comments": 1,
        "pr_reviews": 0,
        "primary_work": "Code review, issue triage, and team collaboration on backend1",
        "key_commits": [
            "Issue comment: branch review coordination",
        ],
        "contribution_period": "Jan 2026",
    },
}

# Calculate equity for each contributor
for key in CONTRIBUTORS:
    CONTRIBUTORS[key]["equity_pct"] = calc_equity(CONTRIBUTORS[key])


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
        "StatValue", parent=styles["Normal"], fontSize=20, textColor=ORANGE,
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=24,
    ))
    styles.add(ParagraphStyle(
        "StatCaption", parent=styles["Normal"], fontSize=9, textColor=GRAY,
        fontName="Helvetica", alignment=TA_CENTER, leading=12,
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
        "EquityBig", parent=styles["Normal"], fontSize=44, textColor=ORANGE,
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=50,
    ))
    styles.add(ParagraphStyle(
        "EquityLabel", parent=styles["Normal"], fontSize=13, textColor=DARK,
        fontName="Helvetica", alignment=TA_CENTER, leading=16,
    ))
    styles.add(ParagraphStyle(
        "EquityBreakdown", parent=styles["Normal"], fontSize=10, textColor=GRAY,
        fontName="Helvetica", alignment=TA_CENTER, leading=14,
    ))
    return styles


def generate_pdf(contributor_data):
    name = contributor_data["name"]
    styles = build_styles()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = name.replace(" ", "_")
    filepath = os.path.join(OUTPUT_DIR, f"Docere_Equity_Grant_{safe_name}.pdf")

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
    story.append(Paragraph("Contributor Equity Grant", styles["DocTitle"]))
    story.append(Paragraph(f"Issued to {name}", styles["Subtitle"]))
    story.append(Paragraph("February 10, 2026  |  Koding-4-Kids, Inc. (d/b/a Docere)", styles["SmallGray"]))
    story.append(Spacer(1, 16))

    # ── Equity Amount (big highlight) ──
    bonus = contributor_data["equity_pct"] - BASE_EQUITY
    breakdown = f"Base: {BASE_EQUITY:.2f}%  +  Statistics bonus: {bonus:.2f}%"

    eq_data = [
        [Paragraph(f"{contributor_data['equity_pct']:.2f}%", styles["EquityBig"])],
        [Spacer(1, 4)],
        [Paragraph("of Docere (Koding-4-Kids, Inc.) equity", styles["EquityLabel"])],
        [Spacer(1, 2)],
        [Paragraph(breakdown, styles["EquityBreakdown"])],
    ]
    eq_table = Table(eq_data, colWidths=[5 * inch], rowHeights=[60, 6, 22, 4, 18])
    eq_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ORANGE_LIGHT),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ("VALIGN", (0, 2), (0, 2), "TOP"),
        ("TOPPADDING", (0, 0), (0, 0), 14),
        ("BOTTOMPADDING", (0, -1), (0, -1), 12),
        ("BOX", (0, 0), (-1, -1), 1.5, ORANGE),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    eq_table.hAlign = "CENTER"
    story.append(eq_table)
    story.append(Spacer(1, 20))

    # ── Contribution Statistics ──
    story.append(Paragraph("Contribution Statistics", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=12))

    # Row 1: values
    row1_vals = [
        Paragraph(str(contributor_data["commits"]), styles["StatValue"]),
        Paragraph(str(len(contributor_data["repos"])), styles["StatValue"]),
        Paragraph(str(contributor_data["prs_opened"]), styles["StatValue"]),
        Paragraph(str(contributor_data["prs_merged"]), styles["StatValue"]),
    ]
    # Row 2: captions
    row1_caps = [
        Paragraph("Commits", styles["StatCaption"]),
        Paragraph("Repositories", styles["StatCaption"]),
        Paragraph("PRs Opened", styles["StatCaption"]),
        Paragraph("PRs Merged", styles["StatCaption"]),
    ]
    # Row 3: values
    row2_vals = [
        Paragraph(str(contributor_data["issues_opened"]), styles["StatValue"]),
        Paragraph(str(contributor_data["issue_comments"]), styles["StatValue"]),
        Paragraph(str(contributor_data["pr_reviews"]), styles["StatValue"]),
        Paragraph("", styles["StatValue"]),
    ]
    # Row 4: captions
    row2_caps = [
        Paragraph("Issues Opened", styles["StatCaption"]),
        Paragraph("Issue Comments", styles["StatCaption"]),
        Paragraph("PR Reviews", styles["StatCaption"]),
        Paragraph("", styles["StatCaption"]),
    ]

    stats_table = Table(
        [row1_vals, row1_caps, row2_vals, row2_caps],
        colWidths=[1.6 * inch] * 4,
        rowHeights=[36, 18, 36, 18],
    )
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ("VALIGN", (0, 1), (-1, 1), "TOP"),
        ("VALIGN", (0, 2), (-1, 2), "BOTTOM"),
        ("VALIGN", (0, 3), (-1, 3), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, BORDER),
        ("BOX", (0, 0), (-1, -1), 1, BORDER),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    stats_table.hAlign = "CENTER"
    story.append(stats_table)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Contribution period: {contributor_data['contribution_period']}",
        styles["SmallGray"],
    ))
    story.append(Spacer(1, 14))

    # ── Repositories ──
    story.append(Paragraph("Repositories Contributed To", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))
    for repo in contributor_data["repos"]:
        story.append(Paragraph(
            f'<bullet>&bull;</bullet> <b>Koding-4-Kids/{repo}</b>',
            styles["BulletItem"]
        ))
    story.append(Spacer(1, 8))

    # ── Key Contributions ──
    story.append(Paragraph("Key Contributions", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph(f"<b>Primary work:</b> {contributor_data['primary_work']}", styles["BodyText2"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Notable contributions:</b>", styles["BodyText2"]))
    for commit in contributor_data["key_commits"]:
        story.append(Paragraph(
            f'<bullet>&bull;</bullet> {commit}',
            styles["BulletItem"]
        ))
    story.append(Spacer(1, 14))

    # ── Equity Breakdown ──
    story.append(Paragraph("Equity Calculation", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))

    d = contributor_data
    calc_rows = [
        ["Component", "Count", "Rate", "Value"],
        ["Base grant (founding team)", "", "", f"{BASE_EQUITY:.2f}%"],
        ["Commits", str(d["commits"]), f"+{BONUS_PER_COMMIT:.2f}% each", f"+{d['commits'] * BONUS_PER_COMMIT:.2f}%"],
        ["PRs merged", str(d["prs_merged"]), f"+{BONUS_PER_PR_MERGED:.2f}% each", f"+{d['prs_merged'] * BONUS_PER_PR_MERGED:.2f}%"],
        ["PRs opened", str(d["prs_opened"]), f"+{BONUS_PER_PR_OPENED:.2f}% each", f"+{d['prs_opened'] * BONUS_PER_PR_OPENED:.2f}%"],
        ["Issues opened", str(d["issues_opened"]), f"+{BONUS_PER_ISSUE:.2f}% each", f"+{d['issues_opened'] * BONUS_PER_ISSUE:.2f}%"],
        ["Issue comments", str(d["issue_comments"]), f"+{BONUS_PER_COMMENT:.2f}% each", f"+{d['issue_comments'] * BONUS_PER_COMMENT:.2f}%"],
        ["Extra repos", str(max(0, len(d["repos"]) - 1)), f"+{BONUS_PER_EXTRA_REPO:.2f}% each", f"+{max(0, len(d['repos']) - 1) * BONUS_PER_EXTRA_REPO:.2f}%"],
        ["", "", "Total", f"{d['equity_pct']:.2f}%"],
    ]
    calc_table = Table(calc_rows, colWidths=[2.2 * inch, 1.0 * inch, 1.5 * inch, 1.3 * inch])
    calc_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), ORANGE),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        # Base row highlight
        ("BACKGROUND", (0, 1), (-1, 1), ORANGE_LIGHT),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        # Total row
        ("BACKGROUND", (0, -1), (-1, -1), ORANGE_LIGHT),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (3, -1), (3, -1), ORANGE),
        ("FONTSIZE", (3, -1), (3, -1), 12),
        # General
        ("FONTSIZE", (0, 1), (-1, -2), 9),
        ("TEXTCOLOR", (0, 1), (-1, -2), DARK),
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 1, BORDER),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, BORDER),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(calc_table)
    story.append(Spacer(1, 14))

    # ── Grant Terms ──
    story.append(Paragraph("Grant Terms", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))

    terms_data = [
        ["Grant Amount", f"{contributor_data['equity_pct']:.2f}% of company equity"],
        ["Grant Type", "Restricted stock grant (or equivalent)"],
        ["Vesting Period", "2 years from grant date"],
        ["Cliff", "6 months"],
        ["Vesting Frequency", "Monthly after cliff"],
        ["Acceleration", "Single-trigger on acquisition (100%)"],
        ["Grant Date", "February 10, 2026"],
        ["Contribution Period", contributor_data["contribution_period"]],
    ]
    terms_table = Table(terms_data, colWidths=[2.2 * inch, 4.5 * inch])
    terms_table.setStyle(TableStyle([
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
    story.append(terms_table)
    story.append(Spacer(1, 14))

    # ── Conditions ──
    story.append(Paragraph("Conditions", styles["SectionHead"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))
    conditions = [
        "Contributor must sign a Contributor Assignment Agreement confirming all code contributed to Koding-4-Kids repositories is assigned to the company.",
        "Contributor must sign a standard Confidentiality and IP Assignment Agreement.",
        "Grant is subject to board approval.",
        "If the contributor ceases all contribution before the cliff date, the grant is forfeited in full.",
    ]
    for i, cond in enumerate(conditions, 1):
        story.append(Paragraph(f"<bullet>{i}.</bullet> {cond}", styles["BulletItem"]))
    story.append(Spacer(1, 24))

    # ── Signature Block ──
    story.append(HRFlowable(width="100%", thickness=1, color=ORANGE, spaceAfter=14))
    sig_data = [
        [
            Paragraph("Accepted by Contributor", styles["SmallGray"]),
            Paragraph("Issued by Docere", styles["SmallGray"]),
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
            Paragraph("Date: _______________", styles["SmallGray"]),
            Paragraph("Date: February 10, 2026", styles["SmallGray"]),
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
        "Formal equity grants should be executed with legal counsel and proper corporate board resolutions. "
        "All percentages are pre-dilution.",
        styles["Footer"]
    ))

    doc.build(story)
    print(f"  Generated: {filepath}")
    return filepath


def send_emails(api_key, from_email="equity@docere.ai"):
    """Send equity grant PDFs via Resend API."""
    import resend
    resend.api_key = api_key

    for gh_user, data in CONTRIBUTORS.items():
        if not data["email"]:
            print(f"  SKIP {data['name']} — no email set")
            continue

        filepath = os.path.join(OUTPUT_DIR, f"Docere_Equity_Grant_{data['name'].replace(' ', '_')}.pdf")
        if not os.path.exists(filepath):
            print(f"  SKIP {data['name']} — PDF not found")
            continue

        with open(filepath, "rb") as f:
            pdf_bytes = f.read()

        import base64
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        params = {
            "from": from_email,
            "to": [data["email"]],
            "subject": f"Docere — Your Contributor Equity Grant ({data['equity_pct']:.2f}%)",
            "html": f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="padding: 24px 0; border-bottom: 2px solid #F15524;">
                    <img src="https://raw.githubusercontent.com/Koding-4-Kids/docere-v2/main/frontend/public/docere-logo.png"
                         alt="Docere" style="height: 36px;" />
                </div>
                <div style="padding: 24px 0;">
                    <h2 style="color: #1A1A1A; margin: 0 0 8px 0;">Hi {data['name'].split()[0]},</h2>
                    <p style="color: #666; font-size: 15px; line-height: 1.6;">
                        Thank you for your contributions to Docere. Your work on the project has been valuable,
                        and we want to recognize it formally.
                    </p>
                    <p style="color: #666; font-size: 15px; line-height: 1.6;">
                        Attached is your <b>Contributor Equity Grant</b> for
                        <span style="color: #F15524; font-weight: bold; font-size: 18px;">{data['equity_pct']:.2f}%</span>
                        of Docere (Koding-4-Kids, Inc.).
                    </p>
                    <p style="color: #666; font-size: 15px; line-height: 1.6;">
                        This includes a 3.00% base grant as a founding team member, plus a
                        {data['equity_pct'] - BASE_EQUITY:.2f}% bonus based on your GitHub contribution statistics
                        ({data['commits']} commits, {data['prs_opened']} PRs, across {len(data['repos'])} repo(s)).
                    </p>
                    <p style="color: #666; font-size: 15px; line-height: 1.6;">
                        The attached PDF has the full breakdown, grant terms, and vesting schedule.
                        Please review and let us know if you have any questions.
                    </p>
                    <p style="color: #1A1A1A; font-size: 15px; margin-top: 24px;">
                        — Youdahe Asfaw<br/>
                        <span style="color: #999; font-size: 13px;">Co-Founder, Docere</span>
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
                    "filename": f"Docere_Equity_Grant_{data['name'].replace(' ', '_')}.pdf",
                    "content": pdf_b64,
                    "type": "application/pdf",
                }
            ],
        }

        try:
            email = resend.Emails.send(params)
            print(f"  SENT to {data['name']} ({data['email']}) — ID: {email.get('id', 'ok')}")
        except Exception as e:
            print(f"  FAILED {data['name']}: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Generating Docere Founding Team Equity Grant PDFs")
    print("=" * 60)
    print()
    print("Equity formula: 3.00% base + stats bonus")
    print(f"  +{BONUS_PER_COMMIT:.2f}% per commit")
    print(f"  +{BONUS_PER_PR_MERGED:.2f}% per merged PR")
    print(f"  +{BONUS_PER_PR_OPENED:.2f}% per opened PR")
    print(f"  +{BONUS_PER_ISSUE:.2f}% per issue")
    print(f"  +{BONUS_PER_COMMENT:.2f}% per comment")
    print(f"  +{BONUS_PER_EXTRA_REPO:.2f}% per extra repo")
    print()

    total = 0
    for gh_user, data in CONTRIBUTORS.items():
        pct = data["equity_pct"]
        total += pct
        print(f"  {data['name']:<20s}  {pct:.2f}%  (base 3.00% + {pct - BASE_EQUITY:.2f}% bonus)")

    print(f"\n  {'TOTAL':<20s}  {total:.2f}%")
    print()

    for gh_user, data in CONTRIBUTORS.items():
        generate_pdf(data)

    print()
    print(f"All PDFs saved to: {OUTPUT_DIR}/")
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "--send":
        api_key = os.environ.get("RESEND_API_KEY")
        from_email = os.environ.get("RESEND_FROM", "equity@docere.ai")
        if not api_key:
            print("ERROR: Set RESEND_API_KEY environment variable")
            sys.exit(1)
        print("Sending emails via Resend...")
        send_emails(api_key, from_email)
    else:
        print("To send emails, run:")
        print("  RESEND_API_KEY=re_xxx python generate_equity_pdfs.py --send")
        print()
        print("First, set emails in the script's CONTRIBUTORS dict.")
