"""Generate Docere team meeting slides — March 17, 2026."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ORANGE = RGBColor(0xF1, 0x55, 0x24)
DARK = RGBColor(0x1A, 0x1A, 0x1A)
GRAY = RGBColor(0x66, 0x66, 0x66)
LIGHT_GRAY = RGBColor(0x99, 0x99, 0x99)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BG_CREAM = RGBColor(0xFA, 0xFA, 0xF7)
ORANGE_LIGHT = RGBColor(0xFD, 0xE8, 0xE0)
GREEN = RGBColor(0x22, 0xC5, 0x5E)
RED = RGBColor(0xEF, 0x44, 0x44)
YELLOW = RGBColor(0xF5, 0x9E, 0x0B)

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

prs = Presentation()
prs.slide_width = SLIDE_WIDTH
prs.slide_height = SLIDE_HEIGHT


def add_bg(slide, color=BG_CREAM):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_orange_bar(slide):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_WIDTH, Inches(0.08)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = ORANGE
    shape.line.fill.background()


def add_footer(slide, text="Koding-4-Kids, Inc. (d/b/a Docere)  •  Team Meeting  •  March 17, 2026"):
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(7.0), Inches(12), Inches(0.4))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(10)
    p.font.color.rgb = LIGHT_GRAY
    p.alignment = PP_ALIGN.CENTER


def add_text_box(slide, left, top, width, height, text, font_size=18, color=DARK, bold=False, alignment=PP_ALIGN.LEFT):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.alignment = alignment
    return tf


def add_bullet_slide(slide, left, top, width, height, items, font_size=16, color=DARK):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = item
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.space_after = Pt(8)
        p.level = 0
    return tf


def add_card(slide, left, top, width, height, title, value, value_color=ORANGE):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = WHITE
    shape.line.color.rgb = RGBColor(0xE5, 0xE5, 0xE0)
    shape.line.width = Pt(1)

    # Value
    add_text_box(slide, left, top + Inches(0.15), width, Inches(0.6),
                 str(value), font_size=36, color=value_color, bold=True, alignment=PP_ALIGN.CENTER)
    # Caption
    add_text_box(slide, left, top + Inches(0.7), width, Inches(0.4),
                 title, font_size=12, color=GRAY, alignment=PP_ALIGN.CENTER)


# ═══════════════════════════════════════════
# SLIDE 1: Title
# ═══════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
add_bg(slide, DARK)

# Orange accent bar at top
shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_WIDTH, Inches(0.08))
shape.fill.solid()
shape.fill.fore_color.rgb = ORANGE
shape.line.fill.background()

# Logo
try:
    slide.shapes.add_picture("frontend/public/docere-logo.png", Inches(5.2), Inches(1.5), Inches(3), Inches(0.75))
except Exception:
    add_text_box(slide, Inches(4.5), Inches(1.5), Inches(4.5), Inches(0.8),
                 "DOCERE", font_size=48, color=ORANGE, bold=True, alignment=PP_ALIGN.CENTER)

add_text_box(slide, Inches(2), Inches(3.0), Inches(9), Inches(1.2),
             "Team Meeting", font_size=48, color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)

add_text_box(slide, Inches(2), Inches(4.2), Inches(9), Inches(0.6),
             "March 17, 2026  •  Koding-4-Kids, Inc.", font_size=20, color=ORANGE, alignment=PP_ALIGN.CENTER)

add_text_box(slide, Inches(2), Inches(5.2), Inches(9), Inches(0.6),
             "GitHub Organization Status & Roadmap", font_size=16, color=LIGHT_GRAY, alignment=PP_ALIGN.CENTER)


# ═══════════════════════════════════════════
# SLIDE 2: Org Overview / Key Numbers
# ═══════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_orange_bar(slide)
add_footer(slide)

add_text_box(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
             "Organization at a Glance", font_size=32, color=DARK, bold=True)

add_text_box(slide, Inches(0.8), Inches(1.0), Inches(10), Inches(0.4),
             "Koding-4-Kids GitHub  •  11 repositories  •  11 members", font_size=14, color=GRAY)

# Stat cards
add_card(slide, Inches(0.8), Inches(1.8), Inches(2.5), Inches(1.2), "Total Repos", "11")
add_card(slide, Inches(3.8), Inches(1.8), Inches(2.5), Inches(1.2), "Active Repos", "1", RED)
add_card(slide, Inches(6.8), Inches(1.8), Inches(2.5), Inches(1.2), "Open PRs", "3", YELLOW)
add_card(slide, Inches(9.8), Inches(1.8), Inches(2.5), Inches(1.2), "Org Members", "11")

add_card(slide, Inches(0.8), Inches(3.4), Inches(2.5), Inches(1.2), "Open Issues (docere-v2)", "20", YELLOW)
add_card(slide, Inches(3.8), Inches(3.4), Inches(2.5), Inches(1.2), "Open Issues (backend1)", "19", YELLOW)
add_card(slide, Inches(6.8), Inches(3.4), Inches(2.5), Inches(1.2), "CI Status", "FAILING", RED)
add_card(slide, Inches(9.8), Inches(3.4), Inches(2.5), Inches(1.2), "Merged This Period", "1", GREEN)

add_text_box(slide, Inches(0.8), Inches(5.0), Inches(11.5), Inches(0.5),
             "All active development is concentrated on docere-v2 — every other repo is dormant.",
             font_size=14, color=GRAY)

# Repo list
add_bullet_slide(slide, Inches(0.8), Inches(5.5), Inches(11.5), Inches(1.5), [
    "Active:  docere-v2 (public) — LangGraph agent, LMS integration, flashcards, Focus Mode",
    "Dormant:  backend1, lesson-page, blossom-code-buddy, dashboard, wl-page, canvas, Blossom-Chat-bot, mockBlossom, MVP, front-end",
], font_size=12, color=GRAY)


# ═══════════════════════════════════════════
# SLIDE 3: docere-v2 — Status
# ═══════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_orange_bar(slide)
add_footer(slide)

add_text_box(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
             "docere-v2 — Current Status", font_size=32, color=DARK, bold=True)

add_text_box(slide, Inches(0.8), Inches(1.2), Inches(5.5), Inches(0.5),
             "Branches", font_size=20, color=ORANGE, bold=True)
add_bullet_slide(slide, Inches(0.8), Inches(1.7), Inches(5.5), Inches(2.5), [
    "main — production (last commit Mar 3)",
    "development — integration branch",
    "staging — pre-production",
    "feature/error-boundary-toast-system — CJ (active)",
    "feature/mobile-responsive-layout — CJ (merged via PR #26)",
    "feature/render-chat-markdown — Kevin (open PR #27)",
], font_size=13, color=DARK)

add_text_box(slide, Inches(7), Inches(1.2), Inches(5.5), Inches(0.5),
             "Recent Commits (main)", font_size=20, color=ORANGE, bold=True)
add_bullet_slide(slide, Inches(7), Inches(1.7), Inches(5.8), Inches(3.0), [
    "Mar 3 — LangGraph agent upgrade, 18 backend stubs, dev docs",
    "Mar 2 — CI/CD pipeline, Dockerfile, deployment workflows",
    "Mar 2 — Flashcard spaced repetition, Focus Mode",
    "Feb 25 — Formulas page, Google Sheets/Excel integration",
    "Feb 21 — Gradebook sync, calendar, instructor dashboard",
    "Feb 21 — Gradebook ingestion docs in README",
], font_size=13, color=DARK)

# CI status warning
shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(4.6), Inches(11.5), Inches(0.8))
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0xFE, 0xF2, 0xF2)
shape.line.color.rgb = RED
shape.line.width = Pt(1.5)
add_text_box(slide, Inches(1.0), Inches(4.7), Inches(11), Inches(0.6),
             "CI/CD Pipeline: Last 5 runs FAILED — needs immediate attention (development + feature branches)",
             font_size=15, color=RED, bold=True)

# Open issues summary
add_text_box(slide, Inches(0.8), Inches(5.7), Inches(11.5), Inches(0.5),
             "20 Open Issues — frontend (3), backend (2), research (6), features (6), infra (3)",
             font_size=14, color=GRAY)


# ═══════════════════════════════════════════
# SLIDE 4: Pull Requests
# ═══════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_orange_bar(slide)
add_footer(slide)

add_text_box(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
             "Pull Requests", font_size=32, color=DARK, bold=True)

# Merged
add_text_box(slide, Inches(0.8), Inches(1.3), Inches(11.5), Inches(0.5),
             "Recently Merged", font_size=20, color=GREEN, bold=True)

shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.9), Inches(11.5), Inches(1.0))
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0xF0, 0xFD, 0xF4)
shape.line.color.rgb = GREEN
shape.line.width = Pt(1)
add_text_box(slide, Inches(1.0), Inches(2.0), Inches(11), Inches(0.8),
             "PR #26 — Mobile chat UX responsive layout (CJ Ackett)\n"
             "+223 / -113 lines  •  7 files  •  Reviewed by Copilot  •  Merged by Kofi (Mar 10)",
             font_size=13, color=DARK)

# Open PRs
add_text_box(slide, Inches(0.8), Inches(3.3), Inches(11.5), Inches(0.5),
             "Open — Awaiting Review", font_size=20, color=YELLOW, bold=True)

# PR #27
shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(3.9), Inches(11.5), Inches(1.0))
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0xFF, 0xFB, 0xEB)
shape.line.color.rgb = YELLOW
shape.line.width = Pt(1)
add_text_box(slide, Inches(1.0), Inches(4.0), Inches(11), Inches(0.8),
             "PR #27 — Lightweight Markdown Renderer for Chat Messages (Kevin Thai)  —  docere-v2\n"
             "Open 11 days  •  Review requested from Youdahe + Kofi  •  REVIEW REQUIRED",
             font_size=13, color=DARK)

# Stale lesson-page PRs
shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.2), Inches(11.5), Inches(1.2))
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0xFE, 0xF2, 0xF2)
shape.line.color.rgb = RED
shape.line.width = Pt(1)
add_text_box(slide, Inches(1.0), Inches(5.3), Inches(11), Inches(1.0),
             "STALE — lesson-page repo (2+ months old)\n"
             "PR #1 — Added border and adaptable lesson changes (CJ Ackett)  •  +1061 / -77\n"
             "PR #2 — Navbar buttons (Kevin Thai)  •  +521 / -741",
             font_size=13, color=DARK)


# ═══════════════════════════════════════════
# SLIDE 5: Contributor Activity
# ═══════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_orange_bar(slide)
add_footer(slide)

add_text_box(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
             "Contributor Activity (Mar 3–17)", font_size=32, color=DARK, bold=True)

contributors = [
    ("CJ Ackett", "Most Active", "Created mobile layout branch, merged PR #26, started error boundary feature", GREEN),
    ("Kofi Osei", "Active", "Reviewed & merged PR #26, pushed to development, commented on issues", GREEN),
    ("Kevin Thai", "Active", "Opened PR #27 (markdown renderer), multiple pushes to feature branch", GREEN),
    ("Youdahe Asfaw", "Moderate", "Last commit to main Mar 3. Requested as reviewer on PR #27", YELLOW),
    ("Luke", "Inactive", "No activity in last 2 weeks. Last: CSRF protection PR (Jan 13)", RED),
    ("Jayviont Haing", "Inactive", "No activity in last 2 weeks. Last: bundle optimization PR (Jan 21)", RED),
    ("Noah Moore", "Inactive", "No recent activity", RED),
    ("Joshua Ekoja", "Inactive", "No recent activity (Blossom chatbot contributor)", RED),
]

y = Inches(1.3)
for name, status, desc, status_color in contributors:
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), y, Inches(11.5), Inches(0.65))
    shape.fill.solid()
    shape.fill.fore_color.rgb = WHITE
    shape.line.color.rgb = RGBColor(0xE5, 0xE5, 0xE0)
    shape.line.width = Pt(0.5)

    add_text_box(slide, Inches(1.0), y + Inches(0.05), Inches(2.2), Inches(0.3),
                 name, font_size=14, color=DARK, bold=True)
    add_text_box(slide, Inches(3.3), y + Inches(0.05), Inches(1.5), Inches(0.3),
                 status, font_size=12, color=status_color, bold=True)
    add_text_box(slide, Inches(1.0), y + Inches(0.33), Inches(11), Inches(0.3),
                 desc, font_size=11, color=GRAY)
    y += Inches(0.72)


# ═══════════════════════════════════════════
# SLIDE 6: Open Issues / What's Left
# ═══════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_orange_bar(slide)
add_footer(slide)

add_text_box(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
             "What's Left — Open Issues", font_size=32, color=DARK, bold=True)

# docere-v2 column
add_text_box(slide, Inches(0.8), Inches(1.2), Inches(5.5), Inches(0.4),
             "docere-v2 (20 issues)", font_size=18, color=ORANGE, bold=True)

add_text_box(slide, Inches(0.8), Inches(1.7), Inches(5.8), Inches(0.4),
             "Frontend", font_size=14, color=DARK, bold=True)
add_bullet_slide(slide, Inches(0.8), Inches(2.0), Inches(5.8), Inches(1.2), [
    "#18  Error boundary & toast notifications",
    "#17  Mobile responsive layout",
    "#16  Render markdown in chat (PR #27 open)",
], font_size=12, color=GRAY)

add_text_box(slide, Inches(0.8), Inches(2.9), Inches(5.8), Inches(0.4),
             "Backend / Infra", font_size=14, color=DARK, bold=True)
add_bullet_slide(slide, Inches(0.8), Inches(3.2), Inches(5.8), Inches(1.5), [
    "#19  Response streaming (SSE)",
    "#15  Unit tests for ML infrastructure",
    "#12  Chunk limits & tiered compression",
    "#13  Student todo + calendar integration",
], font_size=12, color=GRAY)

add_text_box(slide, Inches(0.8), Inches(4.4), Inches(5.8), Inches(0.4),
             "Research", font_size=14, color=DARK, bold=True)
add_bullet_slide(slide, Inches(0.8), Inches(4.7), Inches(5.8), Inches(2.0), [
    "#22  Tutoring quality evaluation rubric",
    "#21  A/B testing statistical analysis",
    "#10  Summarize process reward model papers",
    "#9   Survey AI memory systems",
    "#5-#7  Memory architecture, self-improvement, research paper",
], font_size=12, color=GRAY)

# backend1 column
add_text_box(slide, Inches(7), Inches(1.2), Inches(5.5), Inches(0.4),
             "backend1 (19 issues)", font_size=18, color=ORANGE, bold=True)

add_text_box(slide, Inches(7), Inches(1.7), Inches(5.8), Inches(0.4),
             "Critical / Security", font_size=14, color=RED, bold=True)
add_bullet_slide(slide, Inches(7), Inches(2.0), Inches(5.8), Inches(0.6), [
    "#48  Shop authorization & rate limiting (CRITICAL)",
], font_size=12, color=RED)

add_text_box(slide, Inches(7), Inches(2.5), Inches(5.8), Inches(0.4),
             "Performance / Infra", font_size=14, color=DARK, bold=True)
add_bullet_slide(slide, Inches(7), Inches(2.8), Inches(5.8), Inches(1.8), [
    "#69  Improve lesson generation engine",
    "#68  Evaluate Pinecone alternatives",
    "#67  Replace zero-vector Pinecone queries",
    "#63  Rate limiting & circuit breaker",
    "#61  Parallelize N+1 queries (memory tree)",
    "#60  Parallelize N+1 Pinecone queries (chat)",
], font_size=12, color=GRAY)

add_text_box(slide, Inches(7), Inches(4.3), Inches(5.8), Inches(0.4),
             "Features / Bugs", font_size=14, color=DARK, bold=True)
add_bullet_slide(slide, Inches(7), Inches(4.6), Inches(5.8), Inches(1.8), [
    "#66  Re-enable memory capture routes",
    "#65  Embedding cache cleanup",
    "#55  Fix lesson completion rewards (BUG)",
    "#54  Fix Python imports in Pyodide (BUG)",
    "#51  Implement lesson completion state",
    "#50  Shop purchase & character equipping",
    "#46  Content moderation & profanity filter",
], font_size=12, color=GRAY)


# ═══════════════════════════════════════════
# SLIDE 7: Action Items / Priorities
# ═══════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)
add_orange_bar(slide)
add_footer(slide)

add_text_box(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
             "Action Items & Priorities", font_size=32, color=DARK, bold=True)

# Urgent
add_text_box(slide, Inches(0.8), Inches(1.3), Inches(11.5), Inches(0.4),
             "Urgent", font_size=20, color=RED, bold=True)

urgent_items = [
    "Fix CI/CD pipeline — last 5 runs failing on docere-v2",
    "Review & merge PR #27 (Kevin's markdown renderer) — open 11 days",
    "Address backend1 #48 — shop auth & rate limiting (CRITICAL security)",
]
add_bullet_slide(slide, Inches(1.0), Inches(1.8), Inches(11), Inches(1.5), urgent_items, font_size=15, color=DARK)

# This sprint
add_text_box(slide, Inches(0.8), Inches(3.3), Inches(11.5), Inches(0.4),
             "This Sprint", font_size=20, color=YELLOW, bold=True)

sprint_items = [
    "CJ: Continue error boundary + toast system (issue #18)",
    "Kevin: Address PR #27 feedback, start on next frontend issue",
    "Kofi: Code reviews, development branch integration",
    "Close or archive stale lesson-page PRs (#1, #2)",
]
add_bullet_slide(slide, Inches(1.0), Inches(3.8), Inches(11), Inches(1.5), sprint_items, font_size=15, color=DARK)

# Backlog
add_text_box(slide, Inches(0.8), Inches(5.3), Inches(11.5), Inches(0.4),
             "Backlog", font_size=20, color=GRAY, bold=True)

backlog_items = [
    "SSE streaming (#19), student calendar integration (#13)",
    "Research issues (#5–#10, #21–#22) — need assignment",
    "Re-engage inactive contributors or reassign their issues",
]
add_bullet_slide(slide, Inches(1.0), Inches(5.8), Inches(11), Inches(1.2), backlog_items, font_size=15, color=DARK)


# ═══════════════════════════════════════════
# Save
# ═══════════════════════════════════════════
OUTPUT = "/Users/asfawy/docere-v2/Docere_Team_Meeting_2026-03-17.pptx"
prs.save(OUTPUT)
print(f"Slides saved to: {OUTPUT}")
