"""
Chat History Store - Persist conversations theo workspace.

Luu tru chat sessions tai .synapse/chat_history/ trong workspace.
Format: JSON, moi session la mot file rieng.

Features:
- Moi workspace co history rieng (.synapse/chat_history/)
- Gioi han: MAX_SESSIONS sessions × MAX_MESSAGES messages moi session
- Option de disable luu history (privacy setting)
- Thread-safe via module-level lock
"""

import json
import logging
import threading
from pathlib import Path
from typing import List, Optional

from core.chat.message_types import ChatSession

logger = logging.getLogger(__name__)

# Gioi han de tranh disk blow-up
MAX_SESSIONS = 50
MAX_MESSAGES_PER_SESSION = 100

_history_lock = threading.Lock()


def _get_history_dir(workspace: Path) -> Path:
    """Lay duong dan thu muc chat history cho workspace."""
    return workspace / ".synapse" / "chat_history"


def save_session(
    workspace: Path,
    session: ChatSession,
    history_enabled: bool = True,
) -> bool:
    """
    Luu session vao disk.

    Args:
        workspace: Workspace root path
        session: ChatSession can luu
        history_enabled: Co luu hay khong (privacy setting)

    Returns:
        True neu luu thanh cong
    """
    if not history_enabled:
        return True

    with _history_lock:
        try:
            history_dir = _get_history_dir(workspace)
            history_dir.mkdir(parents=True, exist_ok=True)

            session_file = history_dir / f"{session.session_id}.json"

            # Gioi han messages truoc khi luu
            limited_session = _limit_session_messages(session)
            data = limited_session.to_dict()

            session_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Rotate neu qua nhieu sessions
            _rotate_old_sessions(history_dir)
            return True

        except (OSError, IOError) as e:
            logger.warning("Could not save chat session: %s", e)
            return False


def load_session(workspace: Path, session_id: str) -> Optional[ChatSession]:
    """
    Load session tu disk theo ID.

    Args:
        workspace: Workspace root path
        session_id: ID cua session can load

    Returns:
        ChatSession neu tim thay, None neu khong
    """
    with _history_lock:
        try:
            history_dir = _get_history_dir(workspace)
            session_file = history_dir / f"{session_id}.json"

            if not session_file.exists():
                return None

            content = session_file.read_text(encoding="utf-8")
            data = json.loads(content)
            return ChatSession.from_dict(data)

        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not load chat session %s: %s", session_id, e)
            return None


def list_sessions(workspace: Path) -> List[ChatSession]:
    """
    Lay danh sach tat ca sessions cua workspace (sap xep moi nhat truoc).

    Args:
        workspace: Workspace root path

    Returns:
        List ChatSession sap xep theo updated_at giam dan
    """
    with _history_lock:
        try:
            history_dir = _get_history_dir(workspace)
            if not history_dir.exists():
                return []

            sessions: List[ChatSession] = []
            for session_file in history_dir.glob("*.json"):
                try:
                    content = session_file.read_text(encoding="utf-8")
                    data = json.loads(content)
                    session = ChatSession.from_dict(data)
                    sessions.append(session)
                except (OSError, json.JSONDecodeError) as e:
                    logger.debug(
                        "Skipping corrupt session file %s: %s", session_file, e
                    )
                    continue

            # Sap xep theo updated_at giam dan (moi nhat truoc)
            sessions.sort(key=lambda s: s.updated_at, reverse=True)
            return sessions

        except OSError as e:
            logger.warning("Could not list chat sessions: %s", e)
            return []


def delete_session(workspace: Path, session_id: str) -> bool:
    """
    Xoa mot session theo ID.

    Args:
        workspace: Workspace root path
        session_id: ID cua session can xoa

    Returns:
        True neu xoa thanh cong
    """
    with _history_lock:
        try:
            history_dir = _get_history_dir(workspace)
            session_file = history_dir / f"{session_id}.json"

            if session_file.exists():
                session_file.unlink()
            return True

        except OSError as e:
            logger.warning("Could not delete chat session %s: %s", session_id, e)
            return False


def clear_all_sessions(workspace: Path) -> bool:
    """
    Xoa tat ca sessions cua workspace.

    Args:
        workspace: Workspace root path

    Returns:
        True neu xoa thanh cong
    """
    with _history_lock:
        try:
            history_dir = _get_history_dir(workspace)
            if not history_dir.exists():
                return True

            for session_file in history_dir.glob("*.json"):
                session_file.unlink()
            return True

        except OSError as e:
            logger.warning("Could not clear chat history: %s", e)
            return False


def _limit_session_messages(session: ChatSession) -> ChatSession:
    """
    Gioi han so luong messages de tranh file qua lon.

    Giu lai MAX_MESSAGES_PER_SESSION messages moi nhat.

    Args:
        session: Session goc

    Returns:
        Session moi voi messages da gioi han
    """
    if len(session.messages) <= MAX_MESSAGES_PER_SESSION:
        return session

    limited = ChatSession(
        session_id=session.session_id,
        workspace_path=session.workspace_path,
        created_at=session.created_at,
        updated_at=session.updated_at,
        title=session.title,
    )
    limited.messages = session.messages[-MAX_MESSAGES_PER_SESSION:]
    return limited


def _rotate_old_sessions(history_dir: Path) -> None:
    """
    Xoa cac sessions cu nhat neu vuot qua gioi han MAX_SESSIONS.

    Args:
        history_dir: Thu muc chat history
    """
    try:
        session_files = sorted(
            history_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        # Xoa cac files cu vuot qua gioi han
        for old_file in session_files[MAX_SESSIONS:]:
            try:
                old_file.unlink()
                logger.debug("Rotated old chat session: %s", old_file.name)
            except OSError:
                pass

    except OSError as e:
        logger.debug("Could not rotate sessions: %s", e)
