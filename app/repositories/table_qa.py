from sqlalchemy import select

from app.models.qa import TableQAReview
from app.repositories.base import Repository


class TableQARepository(Repository):
    def get_by_table(self, table_id: str) -> TableQAReview | None:
        stmt = select(TableQAReview).where(TableQAReview.table_id == table_id)
        return self.db.scalar(stmt)

    def list_by_document(self, document_id: str) -> list[TableQAReview]:
        stmt = (
            select(TableQAReview)
            .where(TableQAReview.document_id == document_id)
            .order_by(TableQAReview.updated_at.desc(), TableQAReview.table_id.asc())
        )
        return list(self.db.scalars(stmt))

    def upsert(self, payload: dict) -> TableQAReview:
        review = self.get_by_table(payload["table_id"])
        if review is None:
            review = TableQAReview(**payload)
        else:
            for field, value in payload.items():
                if field == "qa_review_id":
                    continue
                setattr(review, field, value)
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review
