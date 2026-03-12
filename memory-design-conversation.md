# Memory System Design — Conversation Notes

## How would you build true, persistent, detailed memory?

Great question. I already have a basic version — a directory of markdown files I read and write between sessions. But "true" memory is much harder. Here's how I'd think about building it properly:

## What I'd actually want

1. **Semantic retrieval, not just file reads** — right now I load `MEMORY.md` wholesale. Real memory should retrieve *relevant* context for the current task, not everything. A vector database (embeddings + similarity search) would let me surface the right memories given the current conversation.

2. **Structured + unstructured layers**
   - Unstructured: free-form notes, observations, reasoning traces
   - Structured: key-value facts (user preferences, project conventions, decisions made) that are easy to query and update

3. **Memory operations as first-class actions**
   - `remember(fact, context, confidence)` — store something with metadata
   - `recall(query)` — retrieve by semantic similarity
   - `forget(id)` — explicit deletion
   - `update(id, new_fact)` — correction without duplicate accumulation

4. **Decay and confidence scoring** — not all memories should be equal. Things confirmed many times get higher weight. Old, unverified things decay. This prevents stale memories from poisoning future sessions.

5. **Episodic vs. semantic memory distinction**
   - *Episodic*: what happened in past sessions ("last time we worked on X, we hit problem Y")
   - *Semantic*: distilled facts ("this project uses bun, not npm")
   - Episodic should compress into semantic over time

6. **Write-back loop** — at the end of a session, summarize what was learned and merge it into long-term storage, deduplicating and resolving conflicts

## The hard parts

- **Trustworthiness**: I can write wrong things into memory. Without a correction mechanism, errors compound. Every write needs a confidence level and a way to invalidate.
- **Relevance filtering**: Loading too much memory is as bad as loading none — it dilutes context.
- **Cross-session coherence**: If I'm running as multiple instances (e.g. parallel agents), memory writes can conflict.

## What I have now vs. what's missing

| Feature | Current | Ideal |
|---|---|---|
| Persistence | Yes (markdown files) | Yes |
| Semantic retrieval | No (load whole file) | Vector search |
| Confidence/decay | No | Yes |
| Conflict resolution | Manual | Automated merge |
| Structured facts | Partial | First-class |

The gap between "files I write to" and "real memory" is mostly the retrieval and confidence layers. The storage part is already solved — the hard part is knowing *what* to store, *when* to retrieve it, and *how much to trust it*.

---

## How would you prevent writing wrong things into memory, or correct them once discovered?

This is the core hard problem. A few layers of defense:

## Prevention (before writing)

**Write less, not more.** The biggest source of wrong memories is premature conclusions — inferring something from one data point. The fix is a higher evidence threshold before writing:
- Don't write after reading one file. Write after a pattern is confirmed across multiple interactions.
- Tag things with their evidence basis: `confirmed_by: [user_statement, code_observation]` vs. `inferred_from: [single_file_read]`

**Distinguish source types.** A user explicitly saying "always use bun" is more reliable than me inferring it from a lockfile. Memory entries should track *how* I know something, not just what.

**Write facts, not interpretations.** "User said to use bun" is safer than "user prefers bun because they find npm unreliable." The latter adds an inference that could be wrong.

## Detection (catching errors later)

**Surface memories to the user periodically.** If I act on a memory and the user corrects me, that's a signal. But I shouldn't wait for implicit corrections — I should occasionally say "I'm operating on the assumption that X, is that still right?" especially for old or low-confidence entries.

**Contradiction detection.** If new evidence conflicts with a stored memory, flag it rather than silently overwriting or ignoring. Force an explicit resolution.

**Confidence decay over time.** Old memories become less trusted automatically. This doesn't delete them but makes me more likely to verify before acting on them.

## Correction (after an error is found)

**Treat user corrections as mandatory writes.** If someone corrects me mid-session, I update the memory *immediately*, not at end-of-session. The current session's correction is the highest-confidence signal available.

**Trace and fix downstream effects.** One wrong fact can seed other memories built on top of it. When correcting an entry, I should check what other memories cite it as a source and flag those for review too.

**Never silently overwrite — annotate.** Instead of deleting the wrong entry, mark it corrected:
```
fact: "project uses npm"
status: CORRECTED
corrected_by: user_statement (2026-03-11)
replaced_by: "project uses bun"
```
This preserves the history and prevents me from re-inferring the same wrong thing.

## The deeper issue

The real problem is that I have no ground truth to validate against — I can only know something is wrong when a human tells me or when I observe a contradiction. That means:

- I should write with **low initial confidence** and upgrade confidence on confirmation
- I should **never act on a memory without some form of verification** if the stakes are high
- I should make my memory **transparent and auditable** so users can correct it proactively, not just reactively

The goal isn't a perfect memory system — it's one that **fails gracefully and recovers quickly** when it's wrong.
