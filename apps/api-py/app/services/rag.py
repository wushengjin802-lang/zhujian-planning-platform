from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DocumentChunk, FactItem, ReportChapter
from app.services.model_gateway import generate_text


def retrieve_chunks(db: Session, project_id: str, query: str, limit: int = 8) -> list[DocumentChunk]:
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.project_id == project_id).order_by(DocumentChunk.chunk_index)).all()
    terms = [term for term in query.replace("，", " ").replace("、", " ").split() if term]
    if not terms:
        return chunks[:limit]

    def score(chunk: DocumentChunk) -> int:
        return sum(1 for term in terms if term in chunk.content)

    ranked = sorted(chunks, key=score, reverse=True)
    return [chunk for chunk in ranked if score(chunk) > 0][:limit] or chunks[:limit]


def generate_chapter_with_rag(db: Session, chapter: ReportChapter) -> dict:
    facts = db.scalars(
        select(FactItem)
        .where(FactItem.project_id == chapter.project_id, FactItem.status.in_(["已确认", "已锁定"]))
        .order_by(FactItem.id)
        .limit(8)
    ).all()
    chunks = retrieve_chunks(db, chapter.project_id, f"{chapter.title} {' '.join(fact.name for fact in facts)}")
    context = [
        {"type": "fact", "id": fact.id, "name": fact.name, "value": fact.value, "unit": fact.unit, "source": fact.source}
        for fact in facts
    ] + [
        {"type": "chunk", "id": chunk.id, "documentId": chunk.document_id, "locator": chunk.locator, "content": chunk.content}
        for chunk in chunks
    ]
    prompt = f"# {chapter.chapter_no}. {chapter.title}\n请依据已确认事实、资料切片和咨询报告写作规范生成章节初稿。"
    result = generate_text(prompt, context)
    return {"content": result["text"], "mode": result["mode"], "facts": facts, "chunks": chunks, "raw": result.get("raw")}

