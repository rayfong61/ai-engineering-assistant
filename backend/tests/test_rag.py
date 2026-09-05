from app.models import Document, DocumentChunk, Project
from app.models.document import EMBEDDING_DIM
from app.services import rag_service


def _chunk(project_id, document_id, embedding: list[float], content: str) -> DocumentChunk:
    return DocumentChunk(
        document_id=document_id,
        project_id=project_id,
        page=1,
        chunk_index=0,
        content=content,
        embedding=embedding,
    )


def test_retrieval_never_crosses_project(db_session, alice):
    # spec2.md section 14: cross-project retrieval is forbidden. Two chunks
    # with the *same* embedding sit in different projects -- if the
    # project_id filter were ever dropped, querying project_a would return
    # both.
    project_a = Project(name="Project A", created_by=alice["id"])
    project_b = Project(name="Project B", created_by=alice["id"])
    db_session.add_all([project_a, project_b])
    db_session.flush()

    doc_a = Document(
        project_id=project_a.id, uploaded_by=alice["id"], filename="a.pdf",
        storage_path="x", status="ready",
    )
    doc_b = Document(
        project_id=project_b.id, uploaded_by=alice["id"], filename="b.pdf",
        storage_path="x", status="ready",
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    shared_vector = [0.1] * EMBEDDING_DIM
    db_session.add(_chunk(project_a.id, doc_a.id, shared_vector, "content in project A"))
    db_session.add(_chunk(project_b.id, doc_b.id, shared_vector, "content in project B"))
    db_session.flush()

    results = rag_service.retrieve_chunks(
        db_session, str(project_a.id), [0.1] * EMBEDDING_DIM, top_k=5
    )

    assert len(results) == 1
    assert results[0].project_id == project_a.id
    assert results[0].content == "content in project A"


def test_retrieval_orders_by_closest_embedding(db_session, alice):
    project = Project(name="Project", created_by=alice["id"])
    db_session.add(project)
    db_session.flush()

    doc = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="doc.pdf",
        storage_path="x", status="ready",
    )
    db_session.add(doc)
    db_session.flush()

    # Cosine distance is angle-based, not magnitude-based -- a vector that's
    # merely scaled from the query has zero distance, so "near" vs "far"
    # must differ in *direction* to actually exercise the ordering.
    query = [1.0] * EMBEDDING_DIM
    near_vector = [1.0] * EMBEDDING_DIM
    near_vector[0] = 1.2  # same direction as query, still closest
    far_vector = [1.0 if i % 2 == 0 else -1.0 for i in range(EMBEDDING_DIM)]  # near-opposite direction

    far = _chunk(project.id, doc.id, far_vector, "far")
    near = _chunk(project.id, doc.id, near_vector, "near")
    db_session.add_all([far, near])
    db_session.flush()

    results = rag_service.retrieve_chunks(db_session, str(project.id), query, top_k=5)

    assert [r.content for r in results] == ["near", "far"]


def test_retrieval_caps_chunks_per_document(db_session, alice):
    # A single chunk-heavy document filling every slot would starve every
    # other document out of the answer entirely -- this is the scenario
    # that surfaced as "AI only found one document" when a real project had
    # one PDF with far more chunks than another.
    project = Project(name="Project", created_by=alice["id"])
    db_session.add(project)
    db_session.flush()

    doc_big = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="big.pdf",
        storage_path="x", status="ready",
    )
    doc_small = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="small.pdf",
        storage_path="x", status="ready",
    )
    db_session.add_all([doc_big, doc_small])
    db_session.flush()

    query = [1.0] * EMBEDDING_DIM

    # doc_big: five chunks each differing from the query in a single
    # dimension -- all near-perfect matches, would fill top_k alone.
    for i in range(5):
        vector = [1.0] * EMBEDDING_DIM
        vector[0] = 1.01 + i * 0.01
        db_session.add(_chunk(project.id, doc_big.id, vector, f"big-{i}"))

    # doc_small: two chunks that are still good matches but measurably
    # further off (differ across many dimensions, not just one), so they
    # rank below all five of doc_big's chunks on pure similarity.
    for i in range(2):
        small_vector = [1.0] * EMBEDDING_DIM
        for j in range(50):
            small_vector[j] = 0.5 + i * 0.01
        db_session.add(_chunk(project.id, doc_small.id, small_vector, f"small-{i}"))
    db_session.flush()

    results = rag_service.retrieve_chunks(
        db_session, str(project.id), query, top_k=5, max_per_document=3
    )

    assert len(results) == 5
    result_doc_ids = {r.document_id for r in results}
    assert doc_small.id in result_doc_ids
    assert sum(1 for r in results if r.document_id == doc_big.id) == 3


def test_match_document_by_filename_finds_unique_mention(db_session, alice):
    project = Project(name="Project", created_by=alice["id"])
    db_session.add(project)
    db_session.flush()

    target = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="010705022.pdf",
        storage_path="x", status="ready",
    )
    other = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="1427C50B.pdf",
        storage_path="x", status="ready",
    )
    db_session.add_all([target, other])
    db_session.flush()

    matched = rag_service.match_document_by_filename(db_session, str(project.id), "010705022.pdf 這份呢")

    assert matched == target.id


def test_match_document_by_filename_no_mention_returns_none(db_session, alice):
    project = Project(name="Project", created_by=alice["id"])
    db_session.add(project)
    db_session.flush()

    db_session.add(
        Document(
            project_id=project.id, uploaded_by=alice["id"], filename="010705022.pdf",
            storage_path="x", status="ready",
        )
    )
    db_session.flush()

    matched = rag_service.match_document_by_filename(db_session, str(project.id), "第三航廈的設計理念是什麼？")

    assert matched is None


def test_match_document_by_filename_ambiguous_returns_none(db_session, alice):
    project = Project(name="Project", created_by=alice["id"])
    db_session.add(project)
    db_session.flush()

    doc_a = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="report-a.pdf",
        storage_path="x", status="ready",
    )
    doc_b = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="report-b.pdf",
        storage_path="x", status="ready",
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    matched = rag_service.match_document_by_filename(
        db_session, str(project.id), "report-a.pdf 跟 report-b.pdf 有什麼不同？"
    )

    assert matched is None


def test_retrieve_chunks_document_id_restricts_to_that_document(db_session, alice):
    # Even when another document's chunk is a much closer vector match, an
    # explicit document_id (from a filename match) must win -- this is the
    # whole point of the filename-routing fix.
    project = Project(name="Project", created_by=alice["id"])
    db_session.add(project)
    db_session.flush()

    wanted = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="wanted.pdf",
        storage_path="x", status="ready",
    )
    closer = Document(
        project_id=project.id, uploaded_by=alice["id"], filename="closer.pdf",
        storage_path="x", status="ready",
    )
    db_session.add_all([wanted, closer])
    db_session.flush()

    query = [1.0] * EMBEDDING_DIM
    exact_match_vector = [1.0] * EMBEDDING_DIM  # zero cosine distance
    far_vector = [1.0 if i % 2 == 0 else -1.0 for i in range(EMBEDDING_DIM)]

    db_session.add(_chunk(project.id, closer.id, exact_match_vector, "closer content"))
    db_session.add(_chunk(project.id, wanted.id, far_vector, "wanted content"))
    db_session.flush()

    results = rag_service.retrieve_chunks(
        db_session, str(project.id), query, top_k=5, document_id=wanted.id
    )

    assert [r.content for r in results] == ["wanted content"]
