#!/usr/bin/env python3
"""
PDF parser for academic papers.
Uses PyMuPDF (fitz) to extract text, detect structure, and find algorithms/equations.
"""

import re
import os
from pathlib import Path
from typing import List, Optional, Tuple
import httpx

from .extractor import (
    ParsedPaper,
    ParsedSection,
    ExtractedAlgorithm,
    ExtractedEquation,
)

# Try to import fitz (PyMuPDF)
try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False


def get_cache_dir() -> Path:
    """Get the PDF cache directory"""
    cache_dir = Path.home() / '.sherpa' / 'pdfs'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class PDFParser:
    """Parses academic PDFs to extract structured content"""

    def __init__(self):
        if not FITZ_AVAILABLE:
            print("Warning: PyMuPDF not installed. Install with: pip install PyMuPDF")

    def download_pdf(self, arxiv_id: str) -> str:
        """Download PDF from arXiv and return local path"""
        # Clean arxiv ID
        arxiv_id = arxiv_id.replace('arxiv:', '').strip()

        # Check cache first
        cache_dir = get_cache_dir()
        pdf_path = cache_dir / f"{arxiv_id.replace('/', '_')}.pdf"

        if pdf_path.exists():
            print(f"Using cached PDF: {pdf_path}")
            return str(pdf_path)

        # Download from arXiv
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        print(f"Downloading PDF from {pdf_url}...")

        try:
            with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                response = client.get(pdf_url)
                response.raise_for_status()

                with open(pdf_path, 'wb') as f:
                    f.write(response.content)

            print(f"Downloaded to: {pdf_path}")
            return str(pdf_path)

        except Exception as e:
            raise RuntimeError(f"Failed to download PDF: {e}")

    def parse(self, pdf_path: str) -> ParsedPaper:
        """Parse a PDF file and extract structured content"""
        if not FITZ_AVAILABLE:
            raise RuntimeError("PyMuPDF not installed. Install with: pip install PyMuPDF")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(pdf_path)

        # Extract basic info
        title = self._extract_title(doc)
        raw_text = self._extract_all_text(doc)
        abstract = self._extract_abstract(raw_text)

        # Extract structured content
        sections = self._extract_sections(doc, raw_text)
        algorithms = self._extract_algorithms(doc, raw_text)
        equations = self._extract_equations(raw_text)

        # Determine arxiv_id from path
        arxiv_id = ''
        filename = os.path.basename(pdf_path)
        if filename.endswith('.pdf'):
            arxiv_id = filename[:-4].replace('_', '/')

        doc.close()

        return ParsedPaper(
            title=title,
            abstract=abstract,
            sections=sections,
            algorithms=algorithms,
            equations=equations,
            raw_text=raw_text,
            pdf_path=pdf_path,
            arxiv_id=arxiv_id
        )

    def parse_from_arxiv(self, arxiv_id: str) -> ParsedPaper:
        """Download and parse a paper from arXiv"""
        pdf_path = self.download_pdf(arxiv_id)
        return self.parse(pdf_path)

    def _extract_title(self, doc: 'fitz.Document') -> str:
        """Extract paper title from first page"""
        if len(doc) == 0:
            return "Unknown Title"

        first_page = doc[0]
        blocks = first_page.get_text("dict")["blocks"]

        # Title is usually the largest text on first page
        max_size = 0
        title_text = ""

        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span["size"] > max_size:
                            max_size = span["size"]
                            title_text = span["text"]
                        elif span["size"] == max_size:
                            title_text += " " + span["text"]

        return title_text.strip()

    def _extract_all_text(self, doc: 'fitz.Document') -> str:
        """Extract all text from PDF"""
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        return "\n".join(text_parts)

    def _extract_abstract(self, text: str) -> str:
        """Extract abstract from text"""
        # Common patterns for abstract
        patterns = [
            r'Abstract[\s\n]+(.+?)(?=\n\s*\d?\s*\.?\s*Introduction|\n\s*1[\s\.])',
            r'ABSTRACT[\s\n]+(.+?)(?=\n\s*\d?\s*\.?\s*INTRODUCTION|\n\s*1[\s\.])',
            r'Abstract\.?\s*(.+?)(?=\n\n|\n\s*\d)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                abstract = match.group(1).strip()
                # Clean up
                abstract = re.sub(r'\s+', ' ', abstract)
                return abstract[:2000]  # Limit length

        return ""

    def _extract_sections(self, doc: 'fitz.Document', text: str) -> List[ParsedSection]:
        """Extract paper sections"""
        sections = []

        # Common section headers
        section_patterns = [
            (r'(?:^|\n)\s*(\d+\.?\s+Introduction)\s*\n', 'introduction'),
            (r'(?:^|\n)\s*(\d+\.?\s+Related Work)\s*\n', 'related_work'),
            (r'(?:^|\n)\s*(\d+\.?\s+Background)\s*\n', 'background'),
            (r'(?:^|\n)\s*(\d+\.?\s+Method(?:s|ology)?)\s*\n', 'method'),
            (r'(?:^|\n)\s*(\d+\.?\s+Approach)\s*\n', 'method'),
            (r'(?:^|\n)\s*(\d+\.?\s+(?:Our )?Algorithm)\s*\n', 'algorithm'),
            (r'(?:^|\n)\s*(\d+\.?\s+Experiments?)\s*\n', 'experiments'),
            (r'(?:^|\n)\s*(\d+\.?\s+Results?)\s*\n', 'results'),
            (r'(?:^|\n)\s*(\d+\.?\s+Discussion)\s*\n', 'discussion'),
            (r'(?:^|\n)\s*(\d+\.?\s+Conclusion)\s*\n', 'conclusion'),
        ]

        # Find all section headers and their positions
        section_matches = []
        for pattern, section_type in section_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                section_matches.append({
                    'title': match.group(1).strip(),
                    'start': match.end(),
                    'type': section_type
                })

        # Sort by position
        section_matches.sort(key=lambda x: x['start'])

        # Extract content between sections
        for i, match in enumerate(section_matches):
            end_pos = section_matches[i + 1]['start'] if i + 1 < len(section_matches) else len(text)
            content = text[match['start']:end_pos].strip()

            # Estimate page numbers (rough approximation)
            char_per_page = len(text) / len(doc) if len(doc) > 0 else 3000
            start_page = int(match['start'] / char_per_page)
            end_page = int(end_pos / char_per_page)

            sections.append(ParsedSection(
                title=match['title'],
                content=content[:5000],  # Limit content length
                page_numbers=list(range(start_page, end_page + 1)),
                section_type=match['type']
            ))

        return sections

    def _extract_algorithms(self, doc: 'fitz.Document', text: str) -> List[ExtractedAlgorithm]:
        """Extract algorithm blocks from paper"""
        algorithms = []

        # Patterns for algorithm detection
        algo_patterns = [
            # "Algorithm 1: Name" style
            r'Algorithm\s+(\d+)[:\s]+([^\n]+)\n((?:.*?\n)*?)(?=Algorithm\s+\d+|$)',
            # "Algorithm 1 Name" style
            r'Algorithm\s+(\d+)\s+([A-Z][^\n]+)\n((?:.*?\n)*?)(?=Algorithm\s+\d+|$)',
            # Block with Input/Output
            r'(Algorithm[^\n]*)\n((?:.*?(?:Input|Output|Require|Ensure|for|while|if|return).*?\n)+)',
        ]

        for pattern in algo_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                groups = match.groups()

                if len(groups) >= 3:
                    algo_num, name, pseudocode = groups[0], groups[1], groups[2]
                    name = f"Algorithm {algo_num}: {name.strip()}"
                elif len(groups) >= 2:
                    name, pseudocode = groups[0], groups[1]
                else:
                    continue

                # Clean pseudocode
                pseudocode = self._clean_pseudocode(pseudocode)

                if len(pseudocode) > 50:  # Only keep meaningful algorithms
                    # Estimate page number
                    char_per_page = len(text) / len(doc) if len(doc) > 0 else 3000
                    page_num = int(match.start() / char_per_page)

                    algorithms.append(ExtractedAlgorithm(
                        name=name.strip(),
                        pseudocode=pseudocode,
                        description=self._get_context(text, match.start(), 200),
                        page_number=page_num
                    ))

        return algorithms

    def _clean_pseudocode(self, text: str) -> str:
        """Clean up extracted pseudocode"""
        lines = text.strip().split('\n')
        cleaned = []

        for line in lines:
            line = line.strip()
            # Skip empty lines and page numbers
            if not line or re.match(r'^\d+$', line):
                continue
            # Stop at common section headers
            if re.match(r'^\d+\.?\s+[A-Z]', line):
                break
            cleaned.append(line)

        return '\n'.join(cleaned[:30])  # Limit to 30 lines

    def _extract_equations(self, text: str) -> List[ExtractedEquation]:
        """Extract numbered equations"""
        equations = []

        # Patterns for equations
        eq_patterns = [
            # Numbered equations like (1), (2), Eq. 1
            r'([^\n]*?(?:=|:=|≈|∝)[^\n]*?)\s*\((\d+)\)',
            r'(?:Eq(?:uation)?\.?\s*)?(\d+)\s*[:\s]+([^\n]*(?:=|:=)[^\n]*)',
        ]

        # Also look for loss functions, objectives
        loss_patterns = [
            r'(L\s*[=:]\s*[^\n]+)',
            r'((?:loss|objective|minimize|maximize)\s*[=:]\s*[^\n]+)',
        ]

        seen_eqs = set()

        for pattern in eq_patterns + loss_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()

                if len(groups) >= 2:
                    if pattern in eq_patterns[:1]:
                        latex, label = groups[0], groups[1]
                    else:
                        label, latex = groups[0], groups[1]
                else:
                    latex = groups[0]
                    label = None

                latex = latex.strip()

                # Skip duplicates and very short equations
                if latex in seen_eqs or len(latex) < 10:
                    continue
                seen_eqs.add(latex)

                context = self._get_context(text, match.start(), 150)

                equations.append(ExtractedEquation(
                    latex=latex,
                    label=f"Eq. {label}" if label else None,
                    context=context,
                    page_number=0  # Would need doc for accurate page
                ))

        return equations[:20]  # Limit to 20 equations

    def _get_context(self, text: str, position: int, chars: int = 200) -> str:
        """Get surrounding context for a match"""
        start = max(0, position - chars)
        end = min(len(text), position + chars)

        context = text[start:end]
        # Clean up
        context = re.sub(r'\s+', ' ', context).strip()

        return context
