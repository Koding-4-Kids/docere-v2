---
name: Document ingestion UX preferences
description: User wants document uploads to process automatically without manual worker startup, wants visual text preview before committing to collection, and wants a separate collections tab
type: feedback
---

Don't require manual worker startup for document processing. The ARQ worker should run automatically as part of the normal app startup or be embedded in the main process.

**Why:** User had to manually run `python run_worker.py` in a separate terminal to process uploaded documents. This is bad UX — uploads should just work.

**How to apply:** Either start the worker automatically with the backend, or process documents inline/in-process for simpler deployments. Consider running ingestion as a background asyncio task if ARQ isn't running.

Also: the document upload flow should show a visual preview of the extracted text (scrollable reader view) BEFORE adding to the collection. The flow should be: upload → preview text → "Add to My Collection" button → then it chunks/embeds. Collections should be a separate tab on the student side, not just a slide-out panel.
