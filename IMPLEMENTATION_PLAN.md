# Docere v2 ML Infrastructure Fixes — Implementation Plan

## Overview
8 fixes across 10 files to close broken loops in the Memory Layer, Process Verification, and Self-Improvement Loop. No schema migrations needed — all DB fields already exist.

---

## Fix 1: Diversity Filter Bug (Critical)
**Files:** `src/docere/integrations/vector_db/qdrant.py`, `src/docere/core/memory/interaction_store.py`

**Bug:** `selected_embeddings.append(query_embedding)` on lines 105 and 118 of `interaction_store.py` — every entry in `selected_embeddings` is the same query vector. So `cosine_similarity(query, query) = 1.0` always, and only 1 result ever passes the diversity filter.

**Changes:**

### qdrant.py — Add `with_vectors` support to `search()`
- Add param `with_vectors: bool = False` to `search()` (line 51)
- Pass `with_vectors=with_vectors` to `self.client.query_points()` (line 71)
- In the return dict comprehension (line 78-85), conditionally include `"vector": point.vector` when `with_vectors=True`:
```python
result = {
    "id": str(point.id),
    "score": point.score,
    "payload": point.payload,
}
if with_vectors and point.vector:
    result["vector"] = point.vector
```

### interaction_store.py — Use actual result vectors
- Pass `with_vectors=True` to `self.qdrant.search()` (line 79)
- Line 105: Change `selected_embeddings.append(query_embedding)` → `selected_embeddings.append(result.get("vector", query_embedding))`
- Line 111: Change `_cosine_similarity(query_embedding, prev_embedding)` → `_cosine_similarity(result.get("vector", query_embedding), prev_embedding)`
- Line 118: Change `selected_embeddings.append(query_embedding)` → `selected_embeddings.append(result.get("vector", query_embedding))`

---

## Fix 2: Close Grade → Strategy Feedback Loop (Critical)
**Files:** `src/docere/core/verification/process_verifier.py`, `src/docere/core/agent.py`, `src/docere/core/improvement/strategy_archive.py`, `src/docere/core/verification/outcome_tracker.py`

**Bug:** `subsequent_performance` is written by OutcomeTracker but never fed back into strategy selection. UCB1 only sees immediate `composite_score`. Also, `interaction_score_id` is never passed from agent.py to `record_outcome()`.

**Changes:**

### process_verifier.py — Expose score_id on VerificationResult
- Add `score_id: str | None = None` to the `VerificationResult` dataclass (line 68, after `scoring_method`)
- After `await self.db.flush()` (line 162), the `score_record.id` is populated. Set `score_id=str(score_record.id)` in the return on line 172.

### agent.py — Pass score_id to record_outcome
- Line 262-266: Pass `interaction_score_id=verification.score_id` to `self.strategies.record_outcome()`

### strategy_archive.py — Add `incorporate_grade_signal()`
- Add new method after `record_outcome()`:
```python
async def incorporate_grade_signal(
    self,
    interaction_score_id: str,
    grade_percentage: float,
) -> None:
    """Blend a grade signal into the strategy score that produced this interaction."""
    result = await self.db.execute(
        select(StrategyScore).where(
            StrategyScore.interaction_score_id == interaction_score_id
        )
    )
    strategy_score = result.scalar_one_or_none()
    if not strategy_score:
        return

    # Blend: 70% original composite, 30% grade signal
    old_score = strategy_score.score
    blended = old_score * 0.7 + grade_percentage * 0.3
    strategy_score.score = blended

    # Adjust parent strategy's avg_score by the delta
    delta = blended - old_score
    strategy_result = await self.db.execute(
        select(StrategyModel).where(StrategyModel.id == strategy_score.strategy_id)
    )
    strategy = strategy_result.scalar_one_or_none()
    if strategy and strategy.total_uses:
        strategy.avg_score = (strategy.avg_score or 0.0) + delta / strategy.total_uses

    await self.db.flush()
```

### outcome_tracker.py — Call incorporate_grade_signal after linking
- Change `__init__` to accept `strategy_archive: StrategyArchive` param, store as `self.strategy_archive`
- Change return type of `link_grade_to_interactions` from `int` to `tuple[int, list[str]]`
- Collect updated `InteractionScore` IDs in a list
- After updating `subsequent_performance`, call `self.strategy_archive.incorporate_grade_signal(str(interaction_score.id), percentage)` for each
- Return `(updated, updated_ids)`
- Need to update any callers of `link_grade_to_interactions` (check `courses.py` API)

---

## Fix 3: Populate Strategy Context Metadata (High)
**Files:** `src/docere/core/improvement/strategy_archive.py`, `src/docere/core/agent.py`

**Bug:** `StrategyScore.context_metadata` is always `{}` — the strategy evolver has no info about what concepts/contexts each strategy works in.

**Changes:**

### strategy_archive.py — Accept context_metadata in record_outcome()
- Add `context_metadata: dict | None = None` param to `record_outcome()` (line 165)
- Pass `context_metadata=context_metadata or {}` to `StrategyScore()` constructor (line 174)

### agent.py — Supply context when recording outcome
- In `_score_previous_interaction()`, after getting `prev_assistant`, look up the MemoryRecord for that message to get concepts:
```python
from docere.models.memory import MemoryRecord
mem_result = await self.db.execute(
    select(MemoryRecord.concepts).where(
        MemoryRecord.source_message_id == prev_assistant.id
    ).limit(1)
)
concepts = mem_result.scalar_one_or_none() or []
```
- Pass to `record_outcome()`:
```python
context_metadata={
    "concepts": concepts,
    "concept": concepts[0] if concepts else None,
    "student_id": student_id,
    "followup_type": verification.student_followup_type,
}
```

---

## Fix 4: Config Disconnect (Medium)
**File:** `src/docere/core/agent.py`

**Bug:** `retrieve_context()` call on line 103 uses the default `max_tokens=8000` (memory_layer.py line 115), but config says `memory_max_context_tokens=4000`.

**Change:**
- Import settings: `from docere.config import settings`
- Line 103-107: Pass `max_tokens=settings.memory_max_context_tokens` to `self.memory.retrieve_context()`

---

## Fix 5: Concept Canonicalization (Medium)
**Files:** `src/docere/core/memory/memory_layer.py`, `src/docere/core/memory/student_profile.py`

**Bug:** "derivatives", "derivative", "taking derivatives" stored as 3 separate concepts. No normalization.

**Changes:**

### memory_layer.py — Add `_normalize_concept()` helper
- Add at module level (after `_estimate_tokens`):
```python
import re

_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
_ACTION_PREFIX_RE = re.compile(
    r"^(understanding|solving|taking|computing|calculating|finding|using|applying|learning|studying)\s+",
    re.IGNORECASE,
)

def _normalize_concept(name: str) -> str:
    """Canonicalize a concept name: strip articles/action prefixes, depluralize, lowercase."""
    name = name.strip().lower()
    name = _ARTICLE_RE.sub("", name)
    name = _ACTION_PREFIX_RE.sub("", name)
    name = name.strip()
    # Simple depluralization: trailing 's' for words > 4 chars (avoids "gas" → "ga")
    if len(name) > 4 and name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name)
    return name
```

### memory_layer.py — Apply in extract_concepts()
- Line 247: After extracting concepts from JSON, normalize them:
```python
concepts = [_normalize_concept(c) for c in data.get("concepts", []) if c.strip()][:4]
```

### student_profile.py — Apply in _update_concept()
- Import `_normalize_concept` from `memory_layer`
- At top of `_update_concept()` (line 109): `concept_name = _normalize_concept(concept_name)`

---

## Fix 6: Concept Matching in OutcomeTracker (Medium)
**File:** `src/docere/core/verification/outcome_tracker.py`

**Bug:** `concept.lower() in content_lower` — substring match. "for" matches "before", "information", etc.

**Change:**
- Import `re` at top of file
- Rewrite `_content_matches_concepts()`:
```python
def _content_matches_concepts(self, content: str, concepts: list[str]) -> bool:
    content_lower = content.lower()
    for concept in concepts:
        c = concept.lower()
        if " " in c:
            # Multi-word concepts: substring match is fine ("chain rule" is specific enough)
            if c in content_lower:
                return True
        else:
            # Single-word concepts: use word boundary to avoid "for" matching "before"
            if re.search(r"\b" + re.escape(c) + r"\b", content_lower):
                return True
    return False
```

---

## Fix 7: Token Budget Gaps (Low)
**File:** `src/docere/core/memory/memory_layer.py`

**Bug:** `concept_mastery` and `recent_grades` are added to context (lines 197-200) without deducting from the token budget. This means interaction history can overflow.

**Change:**
- After setting `context.concept_mastery` (line 197), estimate and deduct:
```python
# 3. Concept mastery
context.concept_mastery = mastery_dict
if mastery_dict:
    mastery_text = "\n".join(f"- {c}: {l:.0%}" for c, l in mastery_dict.items())
    budget -= _estimate_tokens(mastery_text)

# 4. Recent grades
context.recent_grades = recent_grades
if recent_grades:
    grades_text = "\n".join(
        f"- {g.get('title','')}: {g.get('score','')}/{g.get('max_score','')}"
        for g in recent_grades[:5]
    )
    budget -= _estimate_tokens(grades_text)
budget = max(0, budget)
```

---

## Fix 8: Memory Compression Qdrant Sync (Low)
**Files:** `src/docere/integrations/vector_db/qdrant.py`, `src/docere/core/memory/compressor.py`

**Bug:** When memories are compressed, their Qdrant vectors remain as stale data.

**Changes:**

### qdrant.py — Add `delete_by_ids()`
```python
async def delete_by_ids(
    self,
    collection_name: str,
    point_ids: list[str],
) -> None:
    """Delete specific points by their IDs."""
    if not point_ids:
        return
    await self.client.delete(
        collection_name=collection_name,
        points_selector=models.PointIdsList(points=point_ids),
    )
```

### compressor.py — Delete stale vectors after compression
- In `compress_student_memories()`, after marking originals as compressed (line 117-119), collect embedding_ids and delete from Qdrant:
```python
# Collect embedding IDs for Qdrant cleanup
stale_ids = [mem.embedding_id for mem in batch if mem.embedding_id]

# Mark originals as compressed
for mem in batch:
    mem.is_compressed = True
    mem.compressed_into = summary_record.id

# Remove stale vectors from Qdrant
if stale_ids:
    try:
        collection = f"interactions_{course_id}"
        await self.qdrant.delete_by_ids(collection, stale_ids)
    except Exception:
        logger.warning("Failed to clean stale Qdrant vectors", count=len(stale_ids))
```

---

## Implementation Order

Parallel batch 1 (independent files):
- Fix 1 (diversity filter) — `qdrant.py` + `interaction_store.py`
- Fix 4 (config disconnect) — `agent.py` (one line)
- Fix 5 (concept canonicalization) — `memory_layer.py` + `student_profile.py`
- Fix 6 (concept matching regex) — `outcome_tracker.py`
- Fix 7 (token budget) — `memory_layer.py`

Sequential batch 2 (touches agent.py + strategy_archive.py):
- Fix 2 (grade feedback loop) — `process_verifier.py` + `agent.py` + `strategy_archive.py` + `outcome_tracker.py`
- Fix 3 (context metadata) — `strategy_archive.py` + `agent.py`

Standalone:
- Fix 8 (qdrant sync) — `qdrant.py` + `compressor.py`

## Verification Checklist
- [ ] `python -c "from docere.core.agent import TutoringAgent"` — imports clean
- [ ] `pytest tests/` — existing tests pass
- [ ] Manual: send a message, verify diversity filter returns >1 result in logs
- [ ] Ablation groups still work: `control` bypasses ML, `treatment_memory` gets fixed memory, `treatment_full` gets everything
