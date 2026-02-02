#!/usr/bin/env python3
"""
Session management for implementation coaching.
Tracks progress, conversation history, and state across sessions.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from .knowledge_base import KnowledgeBase


@dataclass
class ImplementationSession:
    """Represents an active implementation session"""

    session_id: str
    paper_id: str
    project_path: str
    status: str = 'planning'
    current_stage: int = 0
    stages: List[Dict] = field(default_factory=list)
    conversation_history: List[Dict] = field(default_factory=list)
    context: Dict = field(default_factory=dict)
    started_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    notes: str = ''

    def add_message(self, role: str, content: str, metadata: Dict = None):
        """Add a message to conversation history"""
        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        })
        self.last_active_at = datetime.now()

    def get_messages_for_claude(self) -> List[Dict]:
        """Get conversation history formatted for Claude API"""
        return [
            {'role': msg['role'], 'content': msg['content']}
            for msg in self.conversation_history
            if msg['role'] in ('user', 'assistant')
        ]

    def get_current_stage(self) -> Optional[Dict]:
        """Get the current stage details"""
        if 0 <= self.current_stage < len(self.stages):
            return self.stages[self.current_stage]
        return None

    def advance_stage(self) -> bool:
        """Move to the next stage"""
        if self.current_stage < len(self.stages) - 1:
            self.current_stage += 1
            self.status = 'in_progress'
            return True
        else:
            self.status = 'completed'
            return False

    def mark_stage_complete(self, notes: str = None, files: List[str] = None):
        """Mark the current stage as completed"""
        if self.stages and self.current_stage < len(self.stages):
            self.stages[self.current_stage]['status'] = 'completed'
            self.stages[self.current_stage]['completed_at'] = datetime.now().isoformat()
            if notes:
                self.stages[self.current_stage]['notes'] = notes
            if files:
                self.stages[self.current_stage]['files_created'] = files

    def to_dict(self) -> Dict:
        """Serialize session to dictionary"""
        return {
            'session_id': self.session_id,
            'paper_id': self.paper_id,
            'project_path': self.project_path,
            'status': self.status,
            'current_stage': self.current_stage,
            'stages': self.stages,
            'conversation_history': self.conversation_history,
            'context': self.context,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_active_at': self.last_active_at.isoformat() if self.last_active_at else None,
            'notes': self.notes
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ImplementationSession':
        """Deserialize session from dictionary"""
        session = cls(
            session_id=data['session_id'],
            paper_id=data['paper_id'],
            project_path=data['project_path'],
            status=data.get('status', 'planning'),
            current_stage=data.get('current_stage', 0),
            stages=data.get('stages', []),
            conversation_history=data.get('conversation_history', []),
            context=data.get('context', {}),
            notes=data.get('notes', '')
        )
        if data.get('started_at'):
            session.started_at = datetime.fromisoformat(data['started_at'])
        if data.get('last_active_at'):
            session.last_active_at = datetime.fromisoformat(data['last_active_at'])
        return session


class SessionManager:
    """Manages implementation sessions with database persistence"""

    def __init__(self, kb: KnowledgeBase = None):
        self.kb = kb or KnowledgeBase()
        self._owns_kb = kb is None  # Track if we created the KB

    def create_session(
        self,
        paper_id: str,
        project_path: str,
        stages: List[Dict] = None
    ) -> ImplementationSession:
        """Start a new implementation session"""
        session_id = str(uuid.uuid4())[:8]

        session = ImplementationSession(
            session_id=session_id,
            paper_id=paper_id,
            project_path=project_path,
            status='planning',
            stages=stages or [],
            started_at=datetime.now(),
            last_active_at=datetime.now()
        )

        # Save to database
        self._save_session_to_db(session)

        return session

    def resume_session(self, session_id: str) -> Optional[ImplementationSession]:
        """Resume an existing session from database"""
        cursor = self.kb.conn.cursor()

        # Get session
        cursor.execute(
            "SELECT * FROM implementation_sessions WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        # Build session object
        session_data = dict(row)
        context = json.loads(session_data.get('context_json') or '{}')

        session = ImplementationSession(
            session_id=session_data['session_id'],
            paper_id=session_data['paper_id'],
            project_path=session_data['project_path'],
            status=session_data['status'],
            current_stage=session_data.get('current_stage', 0),
            context=context,
            notes=session_data.get('notes', '')
        )

        if session_data.get('started_at'):
            session.started_at = datetime.fromisoformat(session_data['started_at'])
        if session_data.get('last_active_at'):
            session.last_active_at = datetime.fromisoformat(session_data['last_active_at'])

        # Load stages
        cursor.execute(
            "SELECT * FROM session_progress WHERE session_id = ? ORDER BY stage_order",
            (session_id,)
        )
        for stage_row in cursor.fetchall():
            stage = dict(stage_row)
            stage['files_created'] = json.loads(stage.get('files_created') or '[]')
            session.stages.append(stage)

        # Load conversation history
        cursor.execute(
            "SELECT * FROM session_messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )
        for msg_row in cursor.fetchall():
            msg = dict(msg_row)
            msg['metadata'] = json.loads(msg.get('metadata_json') or '{}')
            session.conversation_history.append({
                'role': msg['role'],
                'content': msg['content'],
                'timestamp': msg['timestamp'],
                'metadata': msg['metadata']
            })

        return session

    def save_session(self, session: ImplementationSession):
        """Persist session state to database"""
        session.last_active_at = datetime.now()
        self._save_session_to_db(session)
        self._save_stages_to_db(session)
        self._save_messages_to_db(session)

    def _save_session_to_db(self, session: ImplementationSession):
        """Save/update session record"""
        cursor = self.kb.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO implementation_sessions
            (session_id, paper_id, project_path, status, current_stage,
             started_at, last_active_at, notes, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.session_id,
            session.paper_id,
            session.project_path,
            session.status,
            session.current_stage,
            session.started_at.isoformat() if session.started_at else None,
            session.last_active_at.isoformat() if session.last_active_at else None,
            session.notes,
            json.dumps(session.context)
        ))

        self.kb.conn.commit()

    def _save_stages_to_db(self, session: ImplementationSession):
        """Save stage progress"""
        cursor = self.kb.conn.cursor()

        # Clear existing stages for this session
        cursor.execute(
            "DELETE FROM session_progress WHERE session_id = ?",
            (session.session_id,)
        )

        # Insert current stages
        for i, stage in enumerate(session.stages):
            cursor.execute("""
                INSERT INTO session_progress
                (session_id, stage_name, stage_order, status, started_at,
                 completed_at, notes, files_created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                stage.get('stage_name', f'Stage {i+1}'),
                i,
                stage.get('status', 'not_started'),
                stage.get('started_at'),
                stage.get('completed_at'),
                stage.get('notes'),
                json.dumps(stage.get('files_created', []))
            ))

        self.kb.conn.commit()

    def _save_messages_to_db(self, session: ImplementationSession):
        """Save conversation history"""
        cursor = self.kb.conn.cursor()

        # Get existing message count
        cursor.execute(
            "SELECT COUNT(*) FROM session_messages WHERE session_id = ?",
            (session.session_id,)
        )
        existing_count = cursor.fetchone()[0]

        # Only insert new messages
        new_messages = session.conversation_history[existing_count:]

        for msg in new_messages:
            cursor.execute("""
                INSERT INTO session_messages (session_id, role, content, timestamp, metadata_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session.session_id,
                msg['role'],
                msg['content'],
                msg.get('timestamp', datetime.now().isoformat()),
                json.dumps(msg.get('metadata', {}))
            ))

        self.kb.conn.commit()

    def list_sessions(self, status: str = None, paper_id: str = None) -> List[Dict]:
        """List all sessions, optionally filtered"""
        cursor = self.kb.conn.cursor()

        query = "SELECT * FROM implementation_sessions WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if paper_id:
            query += " AND paper_id = ?"
            params.append(paper_id)

        query += " ORDER BY last_active_at DESC"

        cursor.execute(query, params)

        sessions = []
        for row in cursor.fetchall():
            session_data = dict(row)
            # Get paper title for display
            paper = self.kb.get_paper(session_data['paper_id'])
            session_data['paper_title'] = paper['title'] if paper else 'Unknown'
            sessions.append(session_data)

        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all related data"""
        cursor = self.kb.conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM session_messages WHERE session_id = ?",
                (session_id,)
            )
            cursor.execute(
                "DELETE FROM session_progress WHERE session_id = ?",
                (session_id,)
            )
            cursor.execute(
                "DELETE FROM implementation_sessions WHERE session_id = ?",
                (session_id,)
            )
            self.kb.conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False

    def close(self):
        """Clean up resources"""
        if self._owns_kb:
            self.kb.close()
