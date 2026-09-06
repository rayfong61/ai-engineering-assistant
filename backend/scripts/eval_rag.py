"""RAG retrieval accuracy evaluation (spec2.md section 38).

Standalone script, not pytest -- calls the real retrieval path
(embedding_service.embed_query + rag_service.retrieve_chunks) against a
project's already-ingested documents and real Voyage/Postgres data.

Usage:
    docker compose exec backend python scripts/eval_rag.py <project_id>
"""

import json
import sys
import time
from pathlib import Path

import voyageai

from app.core.database import SessionLocal
from app.models import Document
from app.services import embedding_service, rag_service

FIXTURE_PATH = Path(__file__).parent / "rag_eval_fixture.json"
TOP_K = 5

# embed_query has no built-in throttling (unlike embed_documents' batching) --
# a Voyage account with no payment method is capped at 3 RPM, so firing 18
# queries back-to-back hits RateLimitError after the 3rd. 25s (a bit more
# than embed_documents' own 21s) keeps this comfortably under 3/minute even
# accounting for request latency.
QUERY_DELAY_SECONDS = 25


def _embed_query_with_retry(question: str, attempts: int = 3) -> list[float]:
    """The free-tier 3 RPM cap can still be brushed if a prior run's window
    hasn't cleared yet -- retry with a long backoff instead of dying."""
    for attempt in range(1, attempts + 1):
        try:
            return embedding_service.embed_query(question)
        except voyageai.error.RateLimitError:
            if attempt == attempts:
                raise
            print(f"  (rate limited, waiting {QUERY_DELAY_SECONDS * 2}s before retry...)", flush=True)
            time.sleep(QUERY_DELAY_SECONDS * 2)


def evaluate(project_id: str) -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    correct = 0
    try:
        for i, case in enumerate(fixture):
            if i > 0:
                time.sleep(QUERY_DELAY_SECONDS)
            query_embedding = _embed_query_with_retry(case["question"])
            chunks = rag_service.retrieve_chunks(db, project_id, query_embedding, top_k=TOP_K)

            filenames = {}
            if chunks:
                doc_ids = {c.document_id for c in chunks}
                filenames = {
                    d.id: d.filename
                    for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()
                }

            hit = any(
                filenames.get(c.document_id) == case["expected_document"]
                and c.page in case.get("expected_pages", [])
                for c in chunks
            )
            correct += hit

            print(f"[{'CORRECT' if hit else 'INCORRECT'}] {case['id']}: {case['question']}", flush=True)
            print(f"  expected: {case['expected_document']} p.{case.get('expected_pages')}", flush=True)
            print(
                "  top-{}  : {}".format(
                    TOP_K,
                    [f"{filenames.get(c.document_id, '?')} p.{c.page}" for c in chunks],
                ),
                flush=True,
            )
    finally:
        db.close()

    total = len(fixture)
    print(f"\nRetrieval Accuracy = {correct}/{total} = {correct / total:.0%}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/eval_rag.py <project_id>")
        sys.exit(1)
    evaluate(sys.argv[1])
