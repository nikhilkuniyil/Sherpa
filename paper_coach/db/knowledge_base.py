#!/usr/bin/env python3
"""
Knowledge Base for Paper Implementation Coach
Stores curated paper metadata, prerequisites, and difficulty ratings
"""

import sqlite3
import json
from typing import List, Dict, Optional
from pathlib import Path


def get_default_db_path() -> str:
    """Get the default database path relative to project root."""
    # Go up from paper_coach/db/ to project root, then into data/
    project_root = Path(__file__).parent.parent.parent
    return str(project_root / "data" / "papers.db")


class KnowledgeBase:
    """Manages the paper knowledge base"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_default_db_path()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()

        # Papers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                arxiv_id TEXT,
                authors TEXT,
                year INTEGER,
                domain TEXT DEFAULT 'post-training',

                -- Educational metadata
                difficulty TEXT CHECK(difficulty IN ('beginner', 'intermediate', 'advanced')),
                educational_value TEXT CHECK(educational_value IN ('low', 'medium', 'high', 'very_high')),
                production_relevance TEXT CHECK(production_relevance IN ('low', 'medium', 'high', 'very_high')),
                implementation_time_hours TEXT,

                -- Content
                key_concepts TEXT,  -- JSON array
                description TEXT,
                why_implement TEXT,

                -- Links
                pdf_url TEXT,
                github_repos TEXT,  -- JSON array

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Prerequisites table (many-to-many relationship)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prerequisites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                prerequisite_paper_id TEXT NOT NULL,
                importance TEXT CHECK(importance IN ('optional', 'recommended', 'required')),
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id),
                FOREIGN KEY (prerequisite_paper_id) REFERENCES papers(paper_id),
                UNIQUE(paper_id, prerequisite_paper_id)
            )
        """)

        # Implementation stages (for staged learning)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS implementation_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                stage_number INTEGER NOT NULL,
                stage_name TEXT NOT NULL,
                description TEXT,
                estimated_hours INTEGER,
                key_concepts TEXT,  -- JSON array
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id),
                UNIQUE(paper_id, stage_number)
            )
        """)

        self.conn.commit()

    def add_paper(self, paper_data: Dict) -> bool:
        """Add a new paper to the knowledge base"""
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO papers (
                    paper_id, title, arxiv_id, authors, year, domain,
                    difficulty, educational_value, production_relevance,
                    implementation_time_hours, key_concepts, description,
                    why_implement, pdf_url, github_repos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                paper_data['paper_id'],
                paper_data['title'],
                paper_data.get('arxiv_id'),
                paper_data.get('authors'),
                paper_data.get('year'),
                paper_data.get('domain', 'post-training'),
                paper_data.get('difficulty'),
                paper_data.get('educational_value'),
                paper_data.get('production_relevance'),
                paper_data.get('implementation_time_hours'),
                json.dumps(paper_data.get('key_concepts', [])),
                paper_data.get('description'),
                paper_data.get('why_implement'),
                paper_data.get('pdf_url'),
                json.dumps(paper_data.get('github_repos', []))
            ))

            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            print(f"Paper {paper_data['paper_id']} already exists")
            return False

    def add_prerequisite(self, paper_id: str, prerequisite_id: str, importance: str = "recommended"):
        """Add a prerequisite relationship"""
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO prerequisites (paper_id, prerequisite_paper_id, importance)
                VALUES (?, ?, ?)
            """, (paper_id, prerequisite_id, importance))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            print(f"Prerequisite relationship already exists")
            return False

    def get_paper(self, paper_id: str) -> Optional[Dict]:
        """Get paper details by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,))
        row = cursor.fetchone()

        if row:
            paper = dict(row)
            paper['key_concepts'] = json.loads(paper['key_concepts']) if paper['key_concepts'] else []
            paper['github_repos'] = json.loads(paper['github_repos']) if paper['github_repos'] else []
            return paper
        return None

    def get_prerequisites(self, paper_id: str) -> List[Dict]:
        """Get all prerequisites for a paper"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.*, pr.importance
            FROM papers p
            JOIN prerequisites pr ON p.paper_id = pr.prerequisite_paper_id
            WHERE pr.paper_id = ?
            ORDER BY
                CASE pr.importance
                    WHEN 'required' THEN 1
                    WHEN 'recommended' THEN 2
                    WHEN 'optional' THEN 3
                END
        """, (paper_id,))

        prerequisites = []
        for row in cursor.fetchall():
            prereq = dict(row)
            prereq['key_concepts'] = json.loads(prereq['key_concepts']) if prereq['key_concepts'] else []
            prereq['github_repos'] = json.loads(prereq['github_repos']) if prereq['github_repos'] else []
            prerequisites.append(prereq)

        return prerequisites

    def search_papers(self, domain: str = None, difficulty: str = None) -> List[Dict]:
        """Search papers by domain and/or difficulty"""
        cursor = self.conn.cursor()

        query = "SELECT * FROM papers WHERE 1=1"
        params = []

        if domain:
            query += " AND domain = ?"
            params.append(domain)

        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)

        query += " ORDER BY year DESC"

        cursor.execute(query, params)

        papers = []
        for row in cursor.fetchall():
            paper = dict(row)
            paper['key_concepts'] = json.loads(paper['key_concepts']) if paper['key_concepts'] else []
            paper['github_repos'] = json.loads(paper['github_repos']) if paper['github_repos'] else []
            papers.append(paper)

        return papers

    def get_all_papers(self) -> List[Dict]:
        """Get all papers in the knowledge base"""
        return self.search_papers()

    def close(self):
        """Close database connection"""
        self.conn.close()
