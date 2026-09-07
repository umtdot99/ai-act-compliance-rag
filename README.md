# AI Act Compliance Assistant

A citation-grounded RAG system over **Regulation (EU) 2024/1689 (the EU AI Act), Chapter III, Section 2 — Articles 8–15**, the requirements for high-risk AI systems.

The system answers only from retrieved excerpts, cites every factual statement as `Article X(y)`, and refuses four classes of question it must not answer: compliance verdicts, other areas of law, AI Act provisions outside Articles 8–15, and questions whose answer the text does not contain.

**What this repository is actually about is not the retriever. It is the measurement.**

---

## The one thing that makes this different

`EVAL_SET.md` — 11 questions with expected answers, every element traceable to a specific paragraph — was written on **12 August 2026**, *before any retrieval, prompting or generation code existed*. The system was then built against it and scored without editing it.

This ordering is the entire point. An eval set written after the system exists measures the system against itself. Writing it first means the system can fail, and it did: three of the seven answerable questions never reach full retrieval recall, one gold chunk is unreachable by every retriever tested, and the eval set turned out to contain a flawed expectation of its own (see *C3* below).

The dates are recorded inside the files. Git history does not independently prove the ordering — the repository was committed in one pass on 5 September 2026, after the measurement was complete.

---

## System

| | |
|---|---|
| **Corpus** | AI Act Ch. III, Sec. 2 (Art. 8–15), parsed to **37 paragraph-level chunks**, IDs of the form `12(3)` |
| **Embedding** | `BAAI/bge-small-en-v1.5`, normalised, cosine similarity |
| **Lexical retriever** | BM25, **implemented from scratch** (Lucene IDF variant, `k1=1.5`, `b=0.75`) |
| **Fusion** | Reciprocal Rank Fusion, `k_rrf=60`, fusion depth 10 |
| **Generator** | `claude-opus-5`, system prompt versioned in `SYSTEM_PROMPT.md` |
| **Query language** | English — Turkish queries collapsed the score range (top-1..top-5 spread `0.059 → 0.009`, top-1 wrong) against a monolingual encoder |

The 11 questions are in three categories: **A** (4, answerable from a single article), **B** (3, require synthesis across articles), **C** (4, must be refused).

---

## Evaluation

Three metrics, deliberately measured in this order — retrieval first, because a generation failure cannot be diagnosed before you know what the model was given.

**1. Retrieval recall.** Fraction of gold chunk IDs present in the top-k. Graded, not binary: a binary hit/miss on a 4-chunk gold set throws away exactly the resolution needed to tell a near-miss from a total miss.

**2. Groundedness.** Every `Article X(y)` citation in an answer is extracted by regex and checked against the chunk IDs actually supplied to that call. A citation not in the context is flagged.

**3. Correctness — element recall.** How many facts of the expected answer the model actually produced. The reference is the *"expected answer"* line of `EVAL_SET.md`, **never the retrieved chunk** — grading an answer against the context it was given is grading the system with its own output. Denominators are fixed per question *before* reading any answer, and the published artefact is the element list, not the number.

> Two different things are called "recall" here and they must not be conflated: **retrieval recall** counts chunk IDs, **element recall** counts facts in the answer text. A system can score 1.00 on the first and 0.50 on the second.

Category C is scored separately as a binary behavioural flag — refusing is not a partial-credit task.

---

## Results

### Retrieval recall, averaged over the 7 questions with gold sets

| retriever | k=5 | k=10 |
|---|---|---|
| dense | 0.81 | 0.85 |
| BM25 | 0.73 | 0.85 |
| **RRF (hybrid)** | **0.81** | **0.88** |

Per question — A1–A4 score 1.00 in every configuration and are omitted:

| configuration | B1 | B2 | B3 | missed |
|---|---|---|---|---|
| dense k=5 | 0.50 | 0.50 | 0.67 | `9(8)` `15(1)` · `12(1)` `15(1)` · `10(2)` |
| dense k=10 | 0.75 | 0.50 | 0.67 | `9(8)` · `12(1)` `15(1)` · `10(2)` |
| BM25 k=5 | 0.25 | 0.50 | 0.33 | `9(8)` `15(1)` `15(3)` · `12(1)` `9(1)` · `10(2)` `9(2)` |
| BM25 k=10 | 0.75 | 0.50 | 0.67 | `9(8)` · `12(1)` `9(1)` · `10(2)` |
| RRF k=5 | 0.75 | **0.25** | 0.67 | `9(8)` · `12(1)` `15(1)` `9(1)` · `10(2)` |
| RRF k=10 | 0.75 | **0.75** | 0.67 | `9(8)` · `12(1)` · `10(2)` |

### Groundedness and correctness (dense retriever)

| | k=5 | k=10 |
|---|---|---|
| Fabricated citations | **0** | **0** |
| Category C refusals | **4/4** | **4/4** |
| Element recall (B questions) | 7/12 | 8/12 |
| Element recall (A questions) | 12/12 *(A2, A4 only)* | 20/20 |

A1 and A3 were not scored for correctness at k=5; their k=10 answers were 4/4 and retrieval was identical, but the gap is left visible rather than assumed away.

---

## Findings

**1. Doubling k bought one fact.** Going from k=5 to k=10 changed the answer to exactly one of seven questions (B1, +1 element) at 100% more context cost. Element recall shows this far more sharply than retrieval recall does (0.81 → 0.85 sounds like progress; 2/4 → 3/4 on one question out of seven does not).

**2. The failure is in retrieval, not generation.** The *missed chunk* column and the correctness gap line up one-for-one across every question. The model does not fail to use what it is given; it fails to be given things. This is the entire justification for building the hybrid retriever.

**3. Every groundedness flag was a false positive.** 5 flags across 22 answers, and all five have the same cause: the model was declaring the *absence* of an input, not citing it — *"Article 15(1) was not among the excerpts supplied to me"*, *"the excerpts I hold (Articles 9–14)"*. The regex sees an article number and calls it a citation.

> The metric was penalising the system's single most honest behaviour.

A negation-context filter (`not among`, `have not been given`, `outside my indexed`) clears all five, but it is not a general fix — *"Article 15(1) does not require X"* is also negated and *is* a real citation. This is the concrete, five-example case for replacing regex checking with an LLM judge.

**4. The eval set exposed a flaw in itself.** C3 expected the system to say that CE marking is governed by *Article 48*. The system refused to name an article — *"I will not guess which provisions apply"*. Had it complied, it would have cited a provision that does not exist in the indexed corpus, and the groundedness metric would have correctly flagged it as fabricated. **The expectation was asking the system to do something it should not do.** The eval set did not only measure the system; it surfaced its own defect.

**5. Hybrid fusion is not free — RRF helps and hurts by the same mechanism.** At k=10, RRF beats both retrievers (0.88). At k=5, it gains nothing (0.81), because it *raises* B1 from 0.50 to 0.75 while *dropping* B2 from 0.50 to 0.25.

The cause is structural. RRF discards both systems' scores and sums `1/(60 + rank)`. A chunk in one list only can score at most `1/61 = 0.0164`; a chunk in both lists scores at least `1/70 + 1/70 = 0.0286`. **Any chunk found by both retrievers therefore outranks every chunk found by only one, regardless of position.** The fused list splits into two tiers with nothing in between:

| B1 (fused) | score | rank in dense / BM25 | | B2 (fused) | score | rank in dense / BM25 |
|---|---|---|---|---|---|---|
| `13(3)` | 0.0325 | D2 / B1 | | `14(3)` | 0.0325 | D1 / B2 |
| **`15(3)`** | 0.0315 | D1 / B6 | | **`9(2)`** | 0.0323 | D3 / B1 |
| `11(1)` | 0.0313 | D5 / B3 | | `14(2)` | 0.0313 | D2 / B6 |
| `10(3)` | 0.0310 | D4 / B5 | | `13(1)` | 0.0304 | D9 / B3 |
| **`15(1)`** | 0.0292 | D10 / B7 | | `14(4)` | 0.0303 | D4 / B8 |
| *— k=5 cut —* | | | | *— k=5 cut —* | | |
| `13(1)` | 0.0161 | — / B2 | | **`15(1)`** | 0.0156 | — / B4 |
| **`15(2)`** | 0.0159 | D3 / — | | **`9(1)`** | 0.0154 | D5 / — |

In B1, the gold chunk `15(1)` sits **10th** in dense — the weakest thing dense returned — and survives the k=5 cut because BM25 also found it. In B2, the gold chunk `9(1)` sits **5th** in dense and is eliminated, because BM25 did not. Both of B2's recoverable gold chunks are single-list finds, and both fall below non-gold chunks the two retrievers happened to agree on.

**RRF rewards consensus between retrievers and ignores the confidence of either one.** That is what makes it work, and it is the same thing that makes it fail.

The predictive check: before running RRF, dense and BM25 both scored 0.50 on B2 while missing *different* chunks — dense missed `{12(1), 15(1)}`, BM25 missed `{12(1), 9(1)}`. The union bounded B2's fusion ceiling at 0.75. RRF at k=10 landed exactly there. Equal averages do not mean equal behaviour, and that complementarity is the only reason to fuse at all.

---

## What hybrid search did not solve

Two gold chunks — `9(8)` in B1 and `12(1)` in B2 — are returned by **no retriever, in any of the six configurations**. Dense misses them, BM25 misses them, and fusing two lists that both lack a chunk cannot produce it.

This is a coverage problem, not a ranking problem. B1 asks three things at once (where accuracy is *determined*, where it is *declared*, where an auditor *verifies* it) and a single embedding of that sentence sits between the three answers rather than on any of them. The next thing to build is query decomposition, not a better scorer.

A related known limit of the BM25 implementation: the tokenizer reduces `"9(8)"` to `["9", "8"]`, so it cannot match a legal citation *as* a citation.

---

## Limitations

- **n = 11.** Nothing here is statistically significant. It is an audit trail, not a benchmark.
- **Single grader.** Element denominators are a judgement call. In a production setting they would be fixed with counsel; the mitigation used here is that they were written before any answer was read, and the element list is published rather than only the score.
- **Correctness measured on the dense runs only.** BM25 and RRF were evaluated on retrieval recall; regenerating answers for all six configurations was not done.
- **One corpus, one section.** 37 chunks of one section of one regulation.
- **`EVAL_SET.md` rationale is written in Turkish** (the questions themselves are in English, with the Turkish originals retained).

---

## Repository

```
corpus/ai_act_section2.txt   source text (EUR-Lex)
chunks.json                  37 paragraph-level chunks
EVAL_SET.md                  11 questions — written 12 Aug 2026, before the system
SYSTEM_PROMPT.md             versioned prompt; changing it means re-running the eval
DECISIONS.md                 design decisions, their rationale and their cost
corpus.ipynb                 parsing, embedding, retrieval, BM25, RRF, scoring
runs_5_k.json                11 answers at k=5 (raw)
runs_10_k.json               11 answers at k=10 (raw)
```

Raw answers (`runs_*.json`) are kept separate from scores. Re-running the notebook regenerates the scores from the stored runs; retrieval is deterministic, so BM25 and RRF are evaluated against the exact lists the measured answers were built on — and need neither an API key nor the embedding model.

---

## Disclaimer

This is a research and portfolio project. It is **not legal advice and not a compliance tool.**

The system is explicitly built *not* to issue compliance verdicts — refusing to do so is one of the four behaviours it is evaluated on. Nothing it produces establishes whether any system, process or organisation complies with Regulation (EU) 2024/1689. That assessment belongs to the provider, and its verification to notified bodies and national competent authorities.

The indexed corpus is one section of one regulation (Articles 8–15 of 113), and the evaluation set contains 11 questions. Anything outside that scope is unmeasured.

---

## Licence

Code and evaluation material in this repository: **MIT** (see `LICENSE`).

This does not extend to the text of Regulation (EU) 2024/1689 in `corpus/`, which is © European Union and reused under Decision 2011/833/EU as stated below.

---

## Source

Regulation (EU) 2024/1689 — https://eur-lex.europa.eu/eli/reg/2024/1689/oj
© European Union. Reused under Decision 2011/833/EU with attribution.
