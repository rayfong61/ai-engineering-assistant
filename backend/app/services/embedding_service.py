import time
from functools import lru_cache

import voyageai

from app.core.config import VOYAGE_API_KEY, VOYAGE_EMBEDDING_MODEL

# A Voyage account with no payment method on file is capped at 3 RPM / 10K
# TPM (not just a lower ceiling -- our old BATCH_SIZE=100 put ~100k tokens
# in a single request, which fails outright regardless of retries). Chunks
# are ~1000 chars/~1000 tokens each, so 8/batch stays safely under 10K TPM;
# BATCH_DELAY_SECONDS keeps requests under 3/minute. This makes ingestion of
# a large PDF slow (background task, so that's acceptable) but reliable
# without requiring billing to be set up on the Voyage account.
BATCH_SIZE = 8
BATCH_DELAY_SECONDS = 21


@lru_cache
def _client() -> voyageai.Client:
    return voyageai.Client(api_key=VOYAGE_API_KEY)


def embed_documents(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        if i > 0:
            time.sleep(BATCH_DELAY_SECONDS)
        batch = texts[i : i + BATCH_SIZE]
        result = _client().embed(batch, model=VOYAGE_EMBEDDING_MODEL, input_type="document")
        embeddings.extend(result.embeddings)
    return embeddings


def embed_query(text: str) -> list[float]:
    result = _client().embed([text], model=VOYAGE_EMBEDDING_MODEL, input_type="query")
    return result.embeddings[0]
