"""CLI: run the full decomposition pipeline on one book (ARCHITECTURE §10).

    atlas demo            # run the offline fixture end-to-end and print results
    atlas demo --json     # same, machine-readable

The `demo` command uses FakeExtractor + the bundled fixture so the whole
pipeline is exercisable with no key and no network. A real `run <pdf>` command
will land once ingest (PyMuPDF) and ClaudeExtractor are implemented.
"""

from __future__ import annotations

import argparse
import json
import sys

from .evals import evaluate
from .extract import FakeExtractor
from .fixtures import SOURCES, build_fixture_graph, build_gold_graph
from .modality import decide_modality
from .pipeline import run_pipeline


def _run_demo(as_json: bool) -> int:
    extractor = FakeExtractor(build_fixture_graph())
    result = run_pipeline(extractor, "convex-demo", "Convex (demo)", SOURCES)
    report = evaluate(result, build_gold_graph())

    if as_json:
        payload = {
            "ok": result.ok,
            "cycle": result.cycle,
            "learning_order": result.learning_order,
            "grounded_rate": result.verification.grounded_rate,
            "verified_nodes": result.verification.verified_nodes,
            "quarantined_nodes": result.verification.quarantined_nodes,
            "modalities": {
                nid: decide_modality(n.features).modality.value
                for nid, n in ((n.id, n) for n in result.graph.nodes)
            },
            "evals": {
                "node_f1": round(report.nodes.f1, 3),
                "edge_f1": round(report.edges.f1, 3),
                "grounded_rate": round(report.grounded_rate, 3),
                "cycle_count": report.cycle_count,
                "orphan_rate": round(report.orphan_rate, 3),
            },
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if result.ok else 1

    label = {n.id: n.label for n in result.graph.nodes}
    print("Atlas decomposition — fixture demo (deductive)\n")
    print(f"pipeline ok        : {result.ok}")
    print(f"verified nodes     : {len(result.verification.verified_nodes)}")
    print(f"quarantined nodes  : {len(result.verification.quarantined_nodes)}")
    print(f"grounded_rate      : {result.verification.grounded_rate:.2f}")
    print("\nlearning order (topological over DAG edges):")
    for i, nid in enumerate(result.learning_order, 1):
        print(f"  {i}. {label.get(nid, nid)}")
    print("\nmodality per node (rules as code):")
    for n in result.graph.nodes:
        d = decide_modality(n.features)
        print(f"  - {n.label}: {d.modality.value}")
    print("\nevals vs gold set:")
    print("  " + report.summary().replace("\n", "\n  "))
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    demo = sub.add_parser("demo", help="run the offline fixture pipeline")
    demo.add_argument("--json", action="store_true", help="machine-readable output")

    args = parser.parse_args(argv)
    if args.cmd == "demo":
        return _run_demo(args.json)
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
