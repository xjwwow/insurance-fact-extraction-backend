from pathlib import Path

from app.core.config import settings
from app.models.document import Document


class DocumentPreviewService:
    def render_page_preview(self, document: Document, page_no: int) -> Path:
        file_path = Path(document.file_path)
        if not file_path.exists():
            raise FileNotFoundError(file_path)

        cache_root = Path(settings.preview_cache_root) / document.document_id
        cache_root.mkdir(parents=True, exist_ok=True)
        target = cache_root / f"page_{page_no}.png"
        if target.exists():
            return target

        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(file_path))
        if page_no < 1 or page_no > len(pdf):
            raise ValueError(f"page out of range: {page_no}")
        page = pdf[page_no - 1]
        bitmap = page.render(scale=max(float(settings.pdf_render_scale), 2.0))
        image = bitmap.to_pil()
        image.save(target, format="PNG")
        return target
