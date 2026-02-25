# Docere — YC Spring 2026 Application Draft

---

## Founders

### Who writes code, or does other technical work on your product? Was any of it done by a non-founder? Please explain.

I (Youdahe) wrote all of the code. I built the v1 platform from scratch in Node.js/Express — it's been running in 2 middle schools since 2025. I then built the entire v2 agent system in Python/FastAPI: the LTI 1.3 integration, the LMS auto-sync pipeline, the memory layer, the self-improvement loop, and the process verification scorer. Kofi co-leads the research — experiment design, the paper we're writing for AIED 2026, and the ML methodology behind the strategy evolution system. No non-founder has written any code.

---

## Company

### Company name

Docere

### Describe what your company does in 50 characters or less.

AI tutor that learns from student outcomes

### Company URL

[TODO: confirm]

### What is your company going to make?

Docere plugs into a school's existing Moodle or Canvas LMS via LTI. It auto-pulls the teacher's course materials — PDFs, syllabi, assignments — so setup takes zero effort. When a student asks for help, Docere tutors them using Socratic questioning grounded in the actual course content.

It's not just for students. Teachers get a dashboard showing every interaction the agent has with their students — what topics students struggle with, which concepts come up repeatedly, how each student is progressing. The agent can also take actions on behalf of teachers: it can schedule a Google Calendar meeting between a teacher and a struggling student, pull that student's memory profile (what they've been working on, where they're stuck, their grade trajectory), and drop it into the meeting description so the teacher walks in prepared. Teachers go from having zero visibility into how students use AI to having more insight than they've ever had.

Every tutoring session is scored: did the agent guide the student to the answer, or just hand it to them? Those scores get linked to actual student grades pulled from the LMS. Weekly, the system mutates its best teaching strategies and prunes the ones that led to worse outcomes. The tutor gets measurably better over time.

We're live in 2 middle schools today.

---

## Location

### Where do you live now, and where would the company be based after YC?

Saint Peter, USA / San Francisco, USA

### Explain your decision regarding location.

We're at Gustavus Adolphus College in Minnesota. Our 2 pilot schools are here, which is useful for hands-on iteration — I've spent hours in classrooms watching students use the product. After YC we'd move to SF. The edtech buyers, AI talent, and YC network are there.

---

## Progress

### How far along are you?

**Deployed:** Docere v1 is live in 2 middle schools. Students use it for coding lessons with an AI copilot that guides them step-by-step instead of giving answers. Teachers did zero setup.

**Built:** Docere v2 is a complete system, ready for deployment:
- LTI 1.3 launch flow — works with any Moodle or Canvas instance, one click
- Auto-sync pipeline that pulls courses, assignments, grades, student rosters, PDFs, and page content from the LMS automatically
- Vector memory (Qdrant) so the agent retrieves relevant course content when students ask questions
- Process verification that scores every tutoring interaction for pedagogical quality
- Self-improvement loop: weekly evolution of teaching strategies based on grade outcomes
- A/B testing framework for comparing strategies across student groups

**Validated:** $10,000 in pitch competition prize money. Research paper ("Learning Agents That Learn") targeting AIED 2026 in Seoul. A professor at our college is helping with the IRB application to run formal classroom studies.

### How long have each of you been working on this? How much of that has been full-time?

I (Youdahe) started building Docere v1 in early 2024 — over 2 years ago. I got it into 2 middle schools by mid-2025. Kofi joined in mid-2024 to co-lead the research and design the v2 agent architecture. We've been building together for ~1.5 years.

We're both full-time students, so neither of us has been full-time on Docere yet. But we've treated it that way — I've shipped 60+ commits on v2 in the past few months alone, built the entire LTI integration and self-improvement loop while taking a full course load. If accepted, we both go full-time immediately.

[TODO: adjust exact dates if needed]

### What tech stack are you using, or planning to use, to build this product? Include AI models and AI coding tools you use.

**V2 (agent system):** Python 3.12, FastAPI, SQLAlchemy (async) + PostgreSQL, Anthropic Claude API (tutoring + strategy evolution), Qdrant (vector DB), Redis + ARQ (task queue), LTI 1.3, pypdf, Alembic.

**V1 (deployed in schools):** Node.js, Express, MySQL.

**AI models:** Claude for tutoring conversations, material compression, and strategy evolution. Voyage AI for embeddings.

**AI coding tools:** Claude Code daily — feature implementation, debugging, architecture decisions. We built the entire PDF auto-sync pipeline (10 files, 500+ lines) in a single session today.

### Coding agent session

[TODO: Export today's Claude Code session — the PDF auto-sync build. Run /export in Claude Code.]

### Are people using your product?

Yes

### How many active users or customers do you have? How many are paying? Who is paying you the most, and how much do they pay you?

505 students across 2 middle schools (229 at one, 276 at the other). No one is paying yet — both schools are on unpaid pilots. We deployed for free intentionally to get real classroom usage data and grade-outcome evidence before charging. Once we can show that students using Docere perform better on assignments, we have a concrete case to bring to the district office for a paid contract.

### Do you have revenue?

No

### If applying with same idea as previous batch, did anything change?

[TODO: first time applying? leave blank]

### Incubator/accelerator?

[TODO: N/A if none]

---

## Idea

### Why did you pick this idea to work on? Do you have domain expertise in this area? How do you know people need what you're making?

I've spent 2 years building educational software and hundreds of hours in middle school classrooms watching students use AI tools. The pattern is obvious: students paste their homework into ChatGPT, get the answer, learn nothing. Teachers see it happening and can't stop it. The problem isn't that AI can't teach — it's that current AI tutors have no idea whether they actually taught anything, and they never get better.

I have direct experience on both sides. I did ML research at Hugging Face and built cognitive software at Medtronic — so I know how to build AI systems. I also built and deployed a coding education platform in real schools — so I know how teachers actually adopt tools (they don't, unless it's zero effort). Kofi was a software engineer at HashiCorp and published ML research at IEEE for the State of Florida.

We know schools need this because we're in the classrooms. Teachers told us two things: first, students paste homework into ChatGPT and learn nothing. Second, teachers have zero visibility into how students use AI — it's a black box. Docere solves both. Students get a tutor that actually teaches. Teachers get full visibility into every agent-student interaction, plus an agent that takes action for them — scheduling parent-teacher meetings, flagging at-risk students, surfacing which topics the class is struggling with. When teachers saw this, they immediately understood the difference. A professor at our university saw the research and volunteered to help with our IRB application. We didn't pitch him — he came to us.

### Who are your competitors? What do you understand about your business that they don't?

Khanmigo (Khan Academy), ChatGPT/Claude used directly, Cognii, Carnegie Learning.

They all miss the same thing: **tutoring quality is measurable, and a system that measures it can improve itself.**

Khanmigo is a good tutor but it's the same tutor forever. It doesn't track whether its teaching strategies actually led to better grades. ChatGPT has memory now, but remembering facts isn't learning — it doesn't score which interventions worked and evolve its approach based on outcomes.

Docere closes that loop. Score every interaction → link scores to actual grades from the LMS → mutate the best strategies → prune the worst → repeat. No competitor does this.

The other gap: teachers won't adopt a new platform. Docere plugs into their existing Moodle/Canvas in one click via LTI. Auto-pulls all content. Zero setup. Khanmigo requires switching to Khan Academy. We meet teachers where they already are.

### How do or will you make money? How much could you make?

SaaS to school districts, per-student-per-year.

- K-12: $5-15/student/year. A mid-size district (10,000 students) = $50k-150k/year.
- Higher ed: $500-2,000/course/semester.

There are ~50 million K-12 students in the US. At $10/student/year, the US K-12 market alone is $500M/year. Districts already spend $5-20/student/year on tools like IXL and DreamBox. We're a direct replacement that actually improves over time.

Near-term: 10 paying districts within 12 months = ~$500k ARR.

### Which category best applies to your company?

K-12

### Other ideas you considered?

1. **LMS-native outcome analytics layer** — don't build the tutor, just build the scoring + strategy evolution system as a plugin any AI tutor can use. Horizontal play across edtech.

2. **AI research copilot for academic papers** — reads drafts, finds methodological gaps, suggests related work. We know the pain firsthand writing our AIED paper.

---

## Equity

### Have you formed ANY legal entity yet?

[TODO: if no, say No and incorporate via Stripe Atlas before submitting]

### Have you taken any investment yet?

No. We have $10,000 from pitch competition prize money.

### Are you currently fundraising?

No

---

## Curious

### What convinced you to apply to Y Combinator?

We have a working product in real schools, a research paper in progress, and $10k in prize money — but we don't have a network in Silicon Valley and we've never built a company before. YC is the fastest way to go from "deployed in 2 schools" to "deployed in 200 districts." The Spring 2026 batch timing is right — we're ready to go full-time.

[TODO: if anyone encouraged you to apply — a professor, mentor, competition judge — name them here]

### How did you hear about Y Combinator?

Been following YC since high school through Startup School, the podcast, and reading about companies like Stripe and Airbnb that came out of the program.

---

## TODOs Before Submitting

- [ ] Add Kofi as co-founder in the YC portal
- [ ] Get Kofi's founder profile completed (hacked-a-system story, most impressive achievement, things built, competitions/awards)
- [ ] Confirm legal entity status — incorporate Delaware C Corp if not done (Stripe Atlas, 2 days)
- [ ] Record founder video (1 min)
- [ ] Record product demo (2-3 min: LTI launch → auto-sync → student tutoring → self-improvement)
- [ ] Export Claude Code session transcript (today's PDF sync build)
- [ ] Get student usage numbers from the 2 schools (even rough: "~40 students, used 3x/week")
- [ ] Confirm exact timeline (when v1 started, when Kofi joined)
- [ ] Company URL
- [ ] Get a recommendation submitted through YC's system (professor helping with IRB?)
- [ ] Your "hacked a system" story — the Reddit NLP trading play
- [ ] Kofi's "hacked a system" story
