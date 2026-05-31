# atlas-engine

The decomposition engine — the moat. Turns a deductive (math/theorem) book into
a typed, provenance-backed knowledge graph. See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## What's implemented (deterministic core, runs offline)

| Module | Role | ARCHITECTURE § |
|---|---|---|
| `schemas.py` | Typed property-graph: node/edge types, citations, DAG-membership rule | §5 |
| `modality.py` | Modality decision as a pure, auditable function (rules as code) | §6 |
| `verify.py` | Anti-hallucination gate: exact-quote match + groundedness | §4.4 |
| `graph.py` | Assembly, cycle detection, learning-order topological sort | §4.5 |
| `extract.py` | `Extractor` Protocol + `FakeExtractor` + node dedup | §4.3 |
| `pipeline.py` | Orchestration: extract → dedup → verify → assemble | §3–4 |
| `learner.py` | Learner model: BKT mastery + FSRS scheduling + DAG-prior cold start | §7 |
| `active.py` | Active processing: grounded retrieval-practice items per node type | §7 |
| `evals.py` | Precision/recall vs gold, grounded_rate, DAG health | §9 |
| `fixtures.py` | A tiny convex-optimization graph with real source spans | §11 |

Extraction is behind a Protocol. The deterministic core (everything else) needs
no API key and no network, and is fully unit-tested. The real
`ClaudeExtractor` (`claude_extractor.py`) is a stub that plugs into the same
interface once a key + a real book are wired up.

## Quickstart

```bash
cd engine
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -q          # 24 tests, all offline
atlas demo         # run the full pipeline on the bundled fixture
atlas demo --json  # machine-readable
```

`atlas demo` runs extract → dedup → verify → assemble end-to-end and prints the
learning order, per-node modality, grounded recall items, a cold-start learner
walking the dependency frontier to mastery, and evals (node/edge F1,
grounded_rate, cycle count, orphan rate).

## Not yet implemented (needs key / network / a real book)

- `ingest/` — PDF → text + spans + LaTeX (PyMuPDF, Marker/Nougat). Blocked here
  by network policy (book hosts disallowed) — implement where the PDF is reachable.
- `ClaudeExtractor` — multi-agent Claude extraction with structured output,
  citations, and prompt caching. Needs `ANTHROPIC_API_KEY` and `pip install -e ".[claude]"`.
- The FastAPI/Next.js output layer (graph UI + node-level learning). The learner
  model and active-processing layers it will sit on top of are implemented
  (`learner.py`, `active.py`).

> Note on FSRS: `learner.py` implements the FSRS-5 curve with published default
> weights; the behavioral invariants are unit-tested, but validate numeric
> parity against `py-fsrs` before production scheduling.
