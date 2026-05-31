"""Real Claude-backed extractor (ARCHITECTURE §4.3).

This is the multi-agent extraction stub that implements the same `Extractor`
Protocol as `FakeExtractor`. It is intentionally thin and import-guarded: the
engine and its tests never import `anthropic`, so the deterministic core runs
with no key and no network. Fill in the agent prompts/calls when iterating with
a real key against a real book.

Design notes (do these when implementing for real):
  * Use the Anthropic SDK with structured output (tool use) bound to the Pydantic
    schemas in schemas.py, so the model cannot free-wheel.
  * Turn on prompt caching for the book chunks — one book = many calls over the
    same context; this is the lever that makes per-book cost tractable.
  * Emit Citations so every node/edge carries an exact source span; the
    deterministic verify.py gate then enforces groundedness.
  * Split into agents: Segmenter (Haiku) -> Node Extractor (Opus) ->
    Edge Extractor (Opus) -> Verifier (Opus, independent pass).
"""

from __future__ import annotations

from .schemas import KnowledgeGraph


class ClaudeExtractor:
    def __init__(self, model: str = "claude-opus-4-8", api_key: str | None = None):
        self.model = model
        self._api_key = api_key

    def extract(
        self,
        document_id: str,
        title: str,
        sources: dict[tuple[str, int], str],
    ) -> KnowledgeGraph:
        raise NotImplementedError(
            "ClaudeExtractor is a stub. It requires the `anthropic` SDK, an API "
            "key, and the multi-agent prompts described in this module's docstring "
            "and ARCHITECTURE.md §4.3. The deterministic pipeline runs today with "
            "FakeExtractor; swap in this class once a key + a real book are wired up."
        )
