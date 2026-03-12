from sqlalchemy import delete, select

from app.models.canonical import CanonicalTable, DocumentPage
from app.models.document import Document
from app.repositories.base import Repository


class DocumentRepository(Repository):
    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get(self, document_id: str) -> Document | None:
        return self.db.get(Document, document_id)

    def list(self, company_id: str | None = None, limit: int = 20) -> list[Document]:
        stmt = select(Document).order_by(Document.created_at.desc()).limit(limit)
        if company_id:
            stmt = stmt.where(Document.company_id == company_id)
        return list(self.db.scalars(stmt))

    def update_parse_status(self, document: Document, status: str) -> Document:
        document.parse_status = status
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def create_page(self, page: DocumentPage) -> DocumentPage:
        self.db.add(page)
        self.db.commit()
        self.db.refresh(page)
        return page

    def create_table(self, table: CanonicalTable) -> CanonicalTable:
        self.db.add(table)
        self.db.commit()
        self.db.refresh(table)
        return table

    def clear_pages(self, document_id: str) -> None:
        self.db.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
        self.db.commit()

    def clear_tables(self, document_id: str) -> None:
        self.db.execute(delete(CanonicalTable).where(CanonicalTable.document_id == document_id))
        self.db.commit()

    def list_tables(self, document_id: str) -> list[CanonicalTable]:
        stmt = (
            select(CanonicalTable)
            .where(CanonicalTable.document_id == document_id)
            .order_by(CanonicalTable.page_start, CanonicalTable.table_id)
        )
        return list(self.db.scalars(stmt))

    def list_pages(self, document_id: str) -> list[DocumentPage]:
        stmt = (
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_no.asc())
        )
        return list(self.db.scalars(stmt))

    def get_table(self, document_id: str, table_id: str) -> CanonicalTable | None:
        stmt = select(CanonicalTable).where(
            CanonicalTable.document_id == document_id,
            CanonicalTable.table_id == table_id,
        )
        return self.db.scalar(stmt)
