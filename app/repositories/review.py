from sqlalchemy import select

from app.models.validation import ReviewLog
from app.repositories.base import Repository


class ReviewLogRepository(Repository):
    def create(self, review_log: ReviewLog) -> ReviewLog:
        self.db.add(review_log)
        self.db.commit()
        self.db.refresh(review_log)
        return review_log

    def list_by_fact(self, fact_id: str) -> list[ReviewLog]:
        stmt = (
            select(ReviewLog)
            .where(ReviewLog.fact_id == fact_id)
            .order_by(ReviewLog.created_at.desc())
        )
        return list(self.db.scalars(stmt))
