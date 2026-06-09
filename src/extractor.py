from pathlib import Path
from typing import Union


class ResumeExtractor:
    """Extract plain text from resume files."""

    @staticmethod
    def extract(file_path: Union[str, Path]) -> str:
        """Extract text from a file (PDF, DOCX, or TXT)."""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".pdf":
            return ResumeExtractor._extract_pdf(path)
        elif suffix == ".docx":
            return ResumeExtractor._extract_docx(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    @staticmethod
    def _extract_pdf(pdf_path: Path) -> str:
        """Extract text from PDF."""
        try:
            import PyPDF2
            text = []
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
            return "\n".join(text)
        except ImportError:
            raise ImportError("Run: pip install PyPDF2")

    @staticmethod
    def _extract_docx(docx_path: Path) -> str:
        """Extract text from DOCX."""
        try:
            import docx
            doc = docx.Document(docx_path)
            return "\n".join([para.text for para in doc.paragraphs])
        except ImportError:
            raise ImportError("Run: pip install python-docx")
