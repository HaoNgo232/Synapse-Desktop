"""
Tests cho Chat module - core/chat va services/chat modules.

Verify:
1. ChatMessage, ChatSession, ChatContext dataclasses
2. ResponseHandler parse OPX va memory blocks
3. ChatHistoryStore load/save/list sessions

Run: pytest tests/test_chat_feature.py -v
"""

import json
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Dam bao project root trong sys.path
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ============================================================
# Tests cho core/chat/message_types.py
# ============================================================


class TestChatMessage:
    """Test ChatMessage dataclass."""

    def test_default_fields(self):
        """ChatMessage phai co default timestamp va message_id."""
        from core.chat.message_types import ChatMessage

        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp  # khong rong
        assert msg.message_id  # khong rong
        assert msg.metadata == {}

    def test_to_dict_roundtrip(self):
        """to_dict/from_dict roundtrip phai bao toan tat ca fields."""
        from core.chat.message_types import ChatMessage

        msg = ChatMessage(
            role="assistant",
            content="I can help you",
            metadata={"tokens": 10},
        )
        d = msg.to_dict()
        restored = ChatMessage.from_dict(d)

        assert restored.role == msg.role
        assert restored.content == msg.content
        assert restored.timestamp == msg.timestamp
        assert restored.message_id == msg.message_id
        assert restored.metadata == msg.metadata

    def test_from_dict_defaults(self):
        """from_dict phai dung defaults cho missing fields."""
        from core.chat.message_types import ChatMessage

        msg = ChatMessage.from_dict({"role": "user", "content": "Hi"})
        assert msg.role == "user"
        assert msg.content == "Hi"
        assert msg.timestamp  # duoc tao tu default_factory
        assert msg.message_id  # duoc tao tu default_factory


class TestChatSession:
    """Test ChatSession dataclass."""

    def test_add_message_updates_timestamp(self):
        """add_message phai cap nhat updated_at."""
        from core.chat.message_types import ChatMessage, ChatSession

        session = ChatSession()
        old_updated = session.updated_at

        import time
        time.sleep(0.01)  # Tranh timestamp trung

        msg = ChatMessage(role="user", content="Hello")
        session.add_message(msg)

        assert session.messages == [msg]
        assert session.updated_at >= old_updated

    def test_auto_title_from_first_user_message(self):
        """Session phai tu dong dat title tu tin nhan user dau tien."""
        from core.chat.message_types import ChatMessage, ChatSession

        session = ChatSession()
        msg = ChatMessage(role="user", content="How does the auth system work?")
        session.add_message(msg)

        assert session.title == "How does the auth system work?"

    def test_auto_title_truncated_at_60_chars(self):
        """Title phai duoc cat sau 60 ky tu."""
        from core.chat.message_types import ChatMessage, ChatSession

        session = ChatSession()
        long_text = "A" * 80
        msg = ChatMessage(role="user", content=long_text)
        session.add_message(msg)

        assert session.title == "A" * 60 + "..."

    def test_get_history_for_llm_excludes_system(self):
        """get_history_for_llm phai loai bo system messages."""
        from core.chat.message_types import ChatMessage, ChatSession

        session = ChatSession()
        session.messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi!"),
        ]

        history = session.get_history_for_llm()
        assert len(history) == 2
        assert all(m["role"] in ("user", "assistant") for m in history)

    def test_to_dict_from_dict_roundtrip(self):
        """Roundtrip serialization phai bao toan session."""
        from core.chat.message_types import ChatMessage, ChatSession

        session = ChatSession(workspace_path="/tmp/test")
        session.add_message(ChatMessage(role="user", content="Test"))
        session.add_message(ChatMessage(role="assistant", content="Response"))

        d = session.to_dict()
        restored = ChatSession.from_dict(d)

        assert restored.session_id == session.session_id
        assert restored.workspace_path == session.workspace_path
        assert len(restored.messages) == 2
        assert restored.messages[0].content == "Test"
        assert restored.messages[1].content == "Response"


class TestChatContext:
    """Test ChatContext dataclass."""

    def test_is_empty_when_no_content(self):
        """ChatContext phai la empty khi khong co content."""
        from core.chat.message_types import ChatContext

        ctx = ChatContext()
        assert ctx.is_empty()

    def test_is_not_empty_with_file_map(self):
        """ChatContext khong empty khi co file_map."""
        from core.chat.message_types import ChatContext

        ctx = ChatContext(file_map="project/\n  src/")
        assert not ctx.is_empty()

    def test_build_system_prompt_includes_workspace(self):
        """build_system_prompt phai include workspace path."""
        from core.chat.message_types import ChatContext

        ctx = ChatContext(workspace_path="/home/user/project")
        prompt = ctx.build_system_prompt()

        assert "/home/user/project" in prompt

    def test_build_system_prompt_includes_file_map(self):
        """build_system_prompt phai include file map."""
        from core.chat.message_types import ChatContext

        ctx = ChatContext(file_map="project/\n  src/\n    main.py")
        prompt = ctx.build_system_prompt()

        assert "project/" in prompt
        assert "main.py" in prompt

    def test_build_system_prompt_includes_memory(self):
        """build_system_prompt phai include memory khi co."""
        from core.chat.message_types import ChatContext

        ctx = ChatContext(memory="Previous session: worked on auth module")
        prompt = ctx.build_system_prompt()

        assert "Previous session" in prompt

    def test_build_system_prompt_no_empty_sections(self):
        """build_system_prompt khong nen include sections rong."""
        from core.chat.message_types import ChatContext

        ctx = ChatContext()  # Khong co gi
        prompt = ctx.build_system_prompt()

        # Phai co content (system instruction)
        assert len(prompt) > 50
        # Khong nen co sections rong
        assert "## Project Structure\n```\n\n```" not in prompt


# ============================================================
# Tests cho core/chat/response_handler.py
# ============================================================


class TestResponseHandler:
    """Test parse_chat_response function."""

    def test_pure_text_response(self):
        """Response text thuan khong co OPX."""
        from core.chat.response_handler import parse_chat_response

        result = parse_chat_response("This is a plain text response.")

        assert not result.has_opx
        assert not result.has_memory
        assert result.raw_content == "This is a plain text response."
        assert result.opx_result is None

    def test_response_with_opx(self):
        """Response chua OPX blocks phai duoc detect."""
        from core.chat.response_handler import parse_chat_response

        content = """
Here is the fix:

<edit file="src/main.py" op="patch">
<find><<<
old_code()
>>></find>
<put><<<
new_code()
>>></put>
</edit>
"""
        result = parse_chat_response(content)

        assert result.has_opx
        assert result.opx_result is not None

    def test_response_with_actionable_opx(self):
        """Response co OPX hop le phai co has_actionable_opx = True."""
        from core.chat.response_handler import parse_chat_response

        content = """
<edit file="test.txt" op="new">
<put><<<
Hello World
>>></put>
</edit>
"""
        result = parse_chat_response(content)

        assert result.has_opx
        assert result.has_actionable_opx

    def test_response_with_memory_block(self):
        """Response co memory block phai duoc extract."""
        from core.chat.response_handler import parse_chat_response

        content = """
Done!

<synapse_memory>
Implemented auth module with JWT tokens.
Next: implement refresh token endpoint.
</synapse_memory>
"""
        result = parse_chat_response(content)

        assert result.has_memory
        assert result.memory_block is not None
        assert "JWT tokens" in result.memory_block

    def test_empty_response(self):
        """Empty response khong co loi."""
        from core.chat.response_handler import parse_chat_response

        result = parse_chat_response("")

        assert not result.has_opx
        assert not result.has_memory


# ============================================================
# Tests cho services/chat_history_store.py
# ============================================================


class TestChatHistoryStore:
    """Test chat history store functions."""

    def test_save_and_load_session(self, tmp_path):
        """save_session va load_session phai work correctly."""
        from core.chat.message_types import ChatMessage, ChatSession
        from services.chat_history_store import load_session, save_session

        session = ChatSession(workspace_path=str(tmp_path))
        session.add_message(ChatMessage(role="user", content="Hello"))
        session.add_message(ChatMessage(role="assistant", content="Hi!"))

        result = save_session(tmp_path, session)
        assert result is True

        loaded = load_session(tmp_path, session.session_id)
        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert len(loaded.messages) == 2
        assert loaded.messages[0].content == "Hello"

    def test_save_with_history_disabled(self, tmp_path):
        """Khi history_enabled=False, khong nen luu file."""
        from core.chat.message_types import ChatMessage, ChatSession
        from services.chat_history_store import save_session

        session = ChatSession()
        session.add_message(ChatMessage(role="user", content="Hello"))

        result = save_session(tmp_path, session, history_enabled=False)
        assert result is True

        # File khong nen ton tai
        history_dir = tmp_path / ".synapse" / "chat_history"
        assert not history_dir.exists()

    def test_list_sessions_empty(self, tmp_path):
        """list_sessions tra ve empty list khi chua co sessions."""
        from services.chat_history_store import list_sessions

        sessions = list_sessions(tmp_path)
        assert sessions == []

    def test_list_sessions_sorted_by_updated_at(self, tmp_path):
        """list_sessions phai sap xep moi nhat truoc."""
        import time
        from core.chat.message_types import ChatMessage, ChatSession
        from services.chat_history_store import list_sessions, save_session

        session1 = ChatSession(workspace_path=str(tmp_path))
        session1.add_message(ChatMessage(role="user", content="First"))
        save_session(tmp_path, session1)

        time.sleep(0.05)

        session2 = ChatSession(workspace_path=str(tmp_path))
        session2.add_message(ChatMessage(role="user", content="Second"))
        save_session(tmp_path, session2)

        sessions = list_sessions(tmp_path)
        assert len(sessions) == 2
        # session2 la moi hon -> phai o dau
        assert sessions[0].session_id == session2.session_id

    def test_delete_session(self, tmp_path):
        """delete_session phai xoa session khoi disk."""
        from core.chat.message_types import ChatMessage, ChatSession
        from services.chat_history_store import delete_session, load_session, save_session

        session = ChatSession()
        session.add_message(ChatMessage(role="user", content="Hello"))
        save_session(tmp_path, session)

        # Verify ton tai
        loaded = load_session(tmp_path, session.session_id)
        assert loaded is not None

        # Xoa
        delete_session(tmp_path, session.session_id)

        # Verify da bi xoa
        loaded_after = load_session(tmp_path, session.session_id)
        assert loaded_after is None

    def test_clear_all_sessions(self, tmp_path):
        """clear_all_sessions phai xoa tat ca sessions."""
        from core.chat.message_types import ChatMessage, ChatSession
        from services.chat_history_store import clear_all_sessions, list_sessions, save_session

        for i in range(3):
            session = ChatSession()
            session.add_message(ChatMessage(role="user", content=f"Message {i}"))
            save_session(tmp_path, session)

        sessions = list_sessions(tmp_path)
        assert len(sessions) == 3

        clear_all_sessions(tmp_path)

        sessions_after = list_sessions(tmp_path)
        assert len(sessions_after) == 0

    def test_load_nonexistent_session(self, tmp_path):
        """load_session tra ve None khi session khong ton tai."""
        from services.chat_history_store import load_session

        result = load_session(tmp_path, str(uuid.uuid4()))
        assert result is None


# ============================================================
# Tests cho AppSettings chat fields
# ============================================================


class TestAppSettingsChatFields:
    """Test cac chat-related fields trong AppSettings."""

    def test_chat_default_values(self):
        """AppSettings phai co chat default values hop le."""
        from config.app_settings import AppSettings

        settings = AppSettings()
        assert settings.chat_model_id == ""
        assert settings.chat_max_context_tokens == 50000
        assert settings.chat_history_enabled is True

    def test_chat_fields_in_to_dict(self):
        """to_dict phai bao gom chat fields."""
        from config.app_settings import AppSettings

        settings = AppSettings()
        d = settings.to_dict()

        assert "chat_model_id" in d
        assert "chat_max_context_tokens" in d
        assert "chat_history_enabled" in d

    def test_chat_fields_roundtrip(self):
        """Chat settings phai survive roundtrip qua to_dict/from_dict."""
        from config.app_settings import AppSettings

        settings = AppSettings(
            chat_model_id="gpt-4o",
            chat_max_context_tokens=30000,
            chat_history_enabled=False,
        )

        restored = AppSettings.from_dict(settings.to_dict())

        assert restored.chat_model_id == "gpt-4o"
        assert restored.chat_max_context_tokens == 30000
        assert restored.chat_history_enabled is False
