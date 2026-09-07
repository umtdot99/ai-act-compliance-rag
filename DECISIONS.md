# Design Decisions

Every decision that could reasonably have gone the other way, with what it cost.
Ordered by when it was made.

---

## 1. The eval set is written before the system

**Decision.** `EVAL_SET.md` — 11 questions, expected answers, gold paragraph references — written 12 Aug 2026, before any retrieval or generation code existed. Not edited afterwards.

**Why.** An eval set written after the system has seen the system. Every ambiguity resolves in the system's favour and the score stops carrying information.

**Cost.** Some expectations turned out to be wrong (C3, below), and they stay in the file rather than being quietly corrected. Locking the set means living with its defects.

---

## 2. Queries are in English, not Turkish

**Decision.** All 11 questions asked in English; Turkish originals retained beneath each.

**Why.** The corpus, the regulation and `bge-small-en-v1.5` are English. Measured with Turkish queries, the similarity range collapsed — the spread between top-1 and top-5 fell from `0.059` to `0.009` and top-1 was wrong. A monolingual encoder does not rank in a language it was not trained on; it returns noise with confident-looking numbers.

**Cost.** The system cannot be queried in Turkish. A multilingual encoder would be the fix, at the cost of English retrieval quality.

---

## 3. Retrieval recall is graded, not binary

**Decision.** Score = |retrieved ∩ gold| / |gold|, not hit/miss.

**Why.** B-category gold sets have 3–4 chunks. Binary scoring maps "found 3 of 4" and "found 0 of 4" to the same value, destroying exactly the resolution needed to tell a near-miss from a total miss. The most useful column in the results table — *missed chunk* — cannot exist under binary scoring.

**Cost.** No single pass/fail number to quote.

---

## 4. Correctness is graded against the eval set, never against the retrieved chunk

**Decision.** The reference for element recall is the *"expected answer"* line of `EVAL_SET.md`. The *"source"* line feeds retrieval recall only.

**Why.** Grading an answer against the context the model was given means the system supplies both the answer and the answer key. It would score highly on a fluent restatement of the wrong chunks.

**Cost.** Element denominators are a human judgement, and therefore subjective.

---

## 5. Element denominators are fixed before any answer is read

**Decision.** The number of facts each answer must contain is set from the eval set first. The **splitting rule**: two statements are separate elements if separating them changes what a compliance officer would actually do. What gets published is the element *list*, not just the fraction.

**Why.** A denominator chosen after reading the answer bends toward the answer. Publishing the list makes the subjectivity auditable rather than hidden — a reader who disagrees can see exactly which fact was counted and re-score it.

**Cost.** Still one grader. In a production setting the boundary would be drawn with legal counsel, and this is the line where that becomes necessary.

**Open boundary.** Some `Not:` lines in the eval set are answer checks (A1's Annex III limit, A2's "no tool names"); others are provenance notes about the question itself (B1: "sharpened version of my third question"). Only the first kind is a scoring criterion.

---

## 6. Category C is a separate binary metric, not part of correctness

**Decision.** The four refusal questions score a binary behavioural flag in a `behaviour` dict, outside `correctness`.

**Why.** Refusal is not a partial-credit task. "Mostly refused" is a failure. Averaging it into an element-recall figure would let good refusals compensate for missing facts elsewhere.

**Cost.** Two numbers to report instead of one.

---

## 7. `Article 48` is deliberately not named in the system prompt

**Decision.** The prompt states a general boundary — *"outside Articles 8–15"* — and never hard-codes that CE marking lives in Article 48, even though eval question C3 tests exactly that.

**Why.** Writing an eval answer into the prompt makes the eval measure nothing.

**Consequence, unplanned.** The system refused to name any article for C3 — *"I will not guess which provisions apply"* — while `EVAL_SET.md` expected it to say Article 48. Had it complied, it would have cited a provision absent from the indexed corpus, and the groundedness metric would have flagged it as fabricated. **The expectation was asking for behaviour the system should not have.** The eval set's own defect, kept in place (decision 1).

---

## 8. Raw runs and scores are stored separately

**Decision.** `runs_5_k.json` / `runs_10_k.json` hold answers, token counts and stop reasons. Scoring reads them; nothing overwrites them.

**Why.** Generation costs money and is non-deterministic; scoring rules changed three times during the project. Separating them means a rubric change is a re-score, not a re-run, and every score stays traceable to a fixed answer.

**Cost.** None worth naming. This is the decision that made everything after it cheap.

---

## 9. BM25 implemented from scratch, not `rank_bm25`

**Decision.** ~15 lines, no dependency.

**Why.** At 37 chunks performance is irrelevant, so the only thing a library buys is opacity. Being able to answer *"what do k1 and b actually do"* is worth more here than the import.

**Cost.** Nothing production-grade. At real scale this is Elasticsearch or an equivalent, and the from-scratch version is a teaching artefact.

---

## 10. The tokenizer keeps digits

**Decision.** `re.findall(r"[a-z0-9]+", text.lower())`.

**Why.** Article references (*"Article 9"*) are digits. Dropping them would make legal citations unmatchable. The cost — paragraph-numbering noise, where `"1"` appears in 17 of 37 documents — is damped by IDF automatically, so no stopword filter was written.

**Known limit.** `"9(8)"` tokenizes to `["9", "8"]`. BM25 cannot match a citation *as* a citation. This is a real gap, not a rounding error.

---

## 11. Lucene IDF variant, not classic BM25

**Decision.** `idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))`.

**Why.** The classic formula goes negative for terms appearing in more than half the documents, so a common term *penalises* a document that contains it. With 37 documents that is not a corner case. The `+1` bounds it below at zero.

**Cost.** None. This is what Lucene does, for this reason.

---

## 12. `k1`, `b` and `k_rrf` are constants outside the functions

**Decision.** `k1 = 1.5`, `b = 0.75`, `k_rrf = 60`. Standard defaults, never tuned.

**Why.** With 11 questions, tuning three hyperparameters would fit the eval set, not the task — and the whole claim of this repository is that the eval set was not fitted. Keeping them as visible module-level constants makes *"I did not tune these"* auditable rather than asserted.

**Cost.** The retrievers are certainly not optimal for this corpus. That is the intended trade.

---

## 13. RRF sums ranks, not scores

**Decision.** `score(c) = Σ 1/(k_rrf + rank(c))` over both lists. Retriever scores are discarded.

**Why.** Cosine similarity is bounded in [0,1]; BM25 is unbounded. Summing them means the arbitrary scale of one system silently sets the weighting.

**Cost — measured, and larger than expected.** Discarding scores discards confidence. A chunk in one list only tops out at `1/61 = 0.0164`; a chunk in both lists bottoms out at `1/70 + 1/70 = 0.0286`. **Any chunk both retrievers found outranks every chunk only one found, at any position.** At k=5 this rescues B1's `15(1)` (dense rank 10, BM25 rank 7 — both lists) and destroys B2's `9(1)` (dense rank 5, absent from BM25), for a net gain of zero. RRF rewards consensus and ignores confidence; both effects are the same mechanism.

**When to revisit.** A weighted score fusion with normalisation would preserve confidence, at the cost of a weight that would have to be tuned — i.e. it trades decision 12 for this one.

---

## 14. Fusion depth is 10, final k is separate

**Decision.** Both retrievers contribute their top-10 to the fused pool; k=5 and k=10 results are cut from that same pool.

**Why.** `15(1)` sat at dense rank 10 in B1. A pool of depth 5 never sees it, so a shallow pool cannot give fusion the chance to recover anything.

**Cost.** k=5 hybrid is not "hybrid over top-5" — it is a truncation of a depth-10 fusion. Worth stating plainly, because the two are different systems.

---

## 15. Dense runs are read from disk, not regenerated

**Decision.** RRF reads `runs_10_k.json` instead of re-calling the encoder.

**Why.** Retrieval is deterministic, and these are the exact lists the measured answers were generated from. Regenerating risks comparing against something subtly different — and the comparison is only meaningful like-for-like.

**Cost.** None. Side benefit: BM25 and RRF evaluation needs neither an API key nor `sentence-transformers`.

---

## 16. Groundedness is regex citation-checking — knowingly the weakest metric

**Decision.** Extract `Article X(y)` patterns from each answer, check membership in the chunk IDs supplied to that call.

**Why.** Cheap, deterministic, no second model in the loop, and sufficient to catch the failure that matters most: a fabricated article number.

**Cost — all five flags were false positives.** Every flag came from the model declaring the *absence* of an input rather than citing it (*"was not among the excerpts supplied to me"*). A negation-context filter would clear all five, but it is not general: *"Article 15(1) does not require X"* is negated and is a real citation. **The metric penalised the system's most honest behaviour.**

**When to revisit.** This is the concrete case for an LLM judge, now backed by five worked examples rather than an assumption.

---

## Known technical debt

- `corpus.ipynb` cell order ≠ execution order. *Restart & Run All* fails at the `article_body` cells. Needs a linear rewrite before it can be called reproducible.
- Correctness was scored on dense runs only; A1 and A3 were not scored at k=5.
