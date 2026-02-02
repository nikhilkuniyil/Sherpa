#!/usr/bin/env python3
"""
Data classes for extracted paper content.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParsedSection:
    """A section of the paper"""
    title: str
    content: str
    page_numbers: List[int] = field(default_factory=list)
    section_type: str = 'body'  # abstract, introduction, method, algorithm, results, etc.

    def __str__(self) -> str:
        return f"[{self.section_type.upper()}] {self.title}"


@dataclass
class ExtractedAlgorithm:
    """An algorithm extracted from the paper"""
    name: str
    pseudocode: str
    description: str = ''
    page_number: int = 0
    dependencies: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Algorithm: {self.name} (page {self.page_number})"


@dataclass
class ExtractedEquation:
    """An equation extracted from the paper"""
    latex: str
    label: Optional[str] = None  # e.g., "Eq. 3"
    context: str = ''  # Surrounding text explaining the equation
    page_number: int = 0

    def __str__(self) -> str:
        label_str = f" ({self.label})" if self.label else ""
        return f"Equation{label_str}: {self.latex[:50]}..."


@dataclass
class ParsedPaper:
    """Complete parsed content from a paper PDF"""
    title: str
    abstract: str = ''
    sections: List[ParsedSection] = field(default_factory=list)
    algorithms: List[ExtractedAlgorithm] = field(default_factory=list)
    equations: List[ExtractedEquation] = field(default_factory=list)
    raw_text: str = ''
    pdf_path: str = ''
    arxiv_id: str = ''

    def get_section(self, section_type: str) -> Optional[ParsedSection]:
        """Get a section by type"""
        for section in self.sections:
            if section.section_type.lower() == section_type.lower():
                return section
        return None

    def get_algorithm(self, name_or_index) -> Optional[ExtractedAlgorithm]:
        """Get algorithm by name or index"""
        if isinstance(name_or_index, int):
            if 0 <= name_or_index < len(self.algorithms):
                return self.algorithms[name_or_index]
        else:
            for algo in self.algorithms:
                if name_or_index.lower() in algo.name.lower():
                    return algo
        return None

    def get_equation(self, label_or_index) -> Optional[ExtractedEquation]:
        """Get equation by label or index"""
        if isinstance(label_or_index, int):
            if 0 <= label_or_index < len(self.equations):
                return self.equations[label_or_index]
        else:
            for eq in self.equations:
                if eq.label and label_or_index.lower() in eq.label.lower():
                    return eq
        return None

    def summary(self) -> str:
        """Get a summary of parsed content"""
        return (
            f"Title: {self.title}\n"
            f"Sections: {len(self.sections)}\n"
            f"Algorithms: {len(self.algorithms)}\n"
            f"Equations: {len(self.equations)}\n"
            f"Total length: {len(self.raw_text)} chars"
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage"""
        return {
            'title': self.title,
            'abstract': self.abstract,
            'sections': [
                {
                    'title': s.title,
                    'content': s.content,
                    'page_numbers': s.page_numbers,
                    'section_type': s.section_type
                }
                for s in self.sections
            ],
            'algorithms': [
                {
                    'name': a.name,
                    'pseudocode': a.pseudocode,
                    'description': a.description,
                    'page_number': a.page_number,
                    'dependencies': a.dependencies
                }
                for a in self.algorithms
            ],
            'equations': [
                {
                    'latex': e.latex,
                    'label': e.label,
                    'context': e.context,
                    'page_number': e.page_number
                }
                for e in self.equations
            ],
            'raw_text': self.raw_text,
            'pdf_path': self.pdf_path,
            'arxiv_id': self.arxiv_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ParsedPaper':
        """Deserialize from dictionary"""
        paper = cls(
            title=data.get('title', ''),
            abstract=data.get('abstract', ''),
            raw_text=data.get('raw_text', ''),
            pdf_path=data.get('pdf_path', ''),
            arxiv_id=data.get('arxiv_id', '')
        )

        for s in data.get('sections', []):
            paper.sections.append(ParsedSection(
                title=s['title'],
                content=s['content'],
                page_numbers=s.get('page_numbers', []),
                section_type=s.get('section_type', 'body')
            ))

        for a in data.get('algorithms', []):
            paper.algorithms.append(ExtractedAlgorithm(
                name=a['name'],
                pseudocode=a['pseudocode'],
                description=a.get('description', ''),
                page_number=a.get('page_number', 0),
                dependencies=a.get('dependencies', [])
            ))

        for e in data.get('equations', []):
            paper.equations.append(ExtractedEquation(
                latex=e['latex'],
                label=e.get('label'),
                context=e.get('context', ''),
                page_number=e.get('page_number', 0)
            ))

        return paper
