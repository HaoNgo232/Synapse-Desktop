"""
AI Pick Files Worker - Background worker chạy Codex Agent để tự động hóa việc chọn file.

Sử dụng QRunnable + QThreadPool để tương tác với Codex SDK trên secondary thread.
"""

import os
import json
import logging
import re
from typing import List

from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from openai_codex import Codex, CodexConfig, Sandbox

logger = logging.getLogger(__name__)


class AIPickFilesWorkerSignals(QObject):
    """
    Signals để giao tiếp giữa background worker và Main UI thread.
    """

    # Emit khi Agent hoàn thành việc chọn file: (list_of_relative_paths)
    finished = Signal(list)
    # Emit khi có lỗi xảy ra: (error_message)
    error = Signal(str)
    # Emit để cập nhật tiến độ lên UI: (status_text)
    progress = Signal(str)


class AIPickFilesWorker(QRunnable):
    """
    Background worker sử dụng Codex SDK để thám hiểm thư mục và chọn file.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_id: str,
        workspace: str,
        user_instruction: str,
    ) -> None:
        super().__init__()
        self.signals = AIPickFilesWorkerSignals()
        self.setAutoDelete(True)
        self._cancelled = False

        self._api_key = api_key
        self._base_url = base_url
        self._model_id = model_id
        self._workspace = workspace
        self._user_instruction = user_instruction

    def cancel(self) -> None:
        """Yêu cầu worker dừng sớm."""
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        if self._cancelled:
            return

        # Validate input parameters
        instr_trimmed = self._user_instruction.strip()
        if not instr_trimmed:
            self.signals.error.emit("User instruction cannot be empty.")
            return
        if len(instr_trimmed) > 8000:
            self.signals.error.emit(
                "User instruction exceeds maximum length of 8000 characters."
            )
            return
        if "\x00" in instr_trimmed:
            self.signals.error.emit("User instruction contains invalid characters.")
            return

        self.signals.progress.emit("Initializing Codex...")

        # Cấu hình custom provider cho Codex SDK
        provider_id = "synapse_custom"
        config = CodexConfig(
            config_overrides=(
                f'model_provider="{provider_id}"',
                f'model="{self._model_id}"',
                f'model_providers.{provider_id}.name="Synapse Custom Provider"',
                f'model_providers.{provider_id}.base_url="{self._base_url}"',
                f'model_providers.{provider_id}.env_key="AI_API_KEY"',
                f'model_providers.{provider_id}.wire_api="responses"',
            )
        )

        # Thiết lập biến môi trường để Codex SDK sử dụng, lưu lại giá trị cũ để restore
        old_env_key = os.environ.get("AI_API_KEY")
        os.environ["AI_API_KEY"] = self._api_key

        codex = None
        try:
            if self._cancelled:
                return

            codex = Codex(config=config)

            if self._cancelled:
                return

            self.signals.progress.emit("Connecting to Agent...")

            # Khởi chạy thread trong workspace với sandbox read_only để đảm bảo an toàn tuyệt đối
            thread = codex.thread_start(cwd=self._workspace, sandbox=Sandbox.read_only)

            # JSON encode user instruction để tránh prompt injection
            instruction_json = json.dumps(self._user_instruction, ensure_ascii=False)

            # Đọc settings để lấy các thư mục bị loại trừ (excluded patterns)
            from domain.ports.registry import DomainRegistry

            try:
                settings = DomainRegistry.settings()
                excluded_patterns = [
                    p.strip()
                    for p in settings.excluded_folders.split("\n")
                    if p.strip()
                ]
            except Exception:
                excluded_patterns = []

            excluded_patterns_str = "\n".join([f"- {pat}" for pat in excluded_patterns])

            prompt = f"""You are a file selection assistant. Your task is to identify all files in this workspace that are relevant to the user instruction:

USER_INSTRUCTION:
{instruction_json}

EXCLUDED_PATTERNS (Do NOT scan, access, view, or suggest any paths matching these patterns):
{excluded_patterns_str}

Selection Philosophy:
- It is better to be slightly over-inclusive than under-inclusive. If you suspect a file might be relevant or helpful for context, include it in the paths list.

Please explore the workspace using directory listing, file viewing, or search tools to find relevant files.
Once you have identified the relevant files, output a single JSON object containing a list of relative file paths.
The format MUST strictly follow this JSON structure:
{{
  "paths": [
    "relative/path/to/file1.py",
    "relative/path/to/file2.py"
  ]
}}

DO NOT write any files to the workspace (you are in a read-only sandbox).
Return ONLY the JSON object and absolutely nothing else. Do not include markdown formatting or explanations.
"""
            if self._cancelled:
                return

            self.signals.progress.emit("AI Selecting...")

            # Chạy agent turn (sử dụng stream để emit progress)
            turn = thread.turn(prompt)
            stream = turn.stream()
            try:
                result = self._collect_stream_with_progress(stream, turn.id)
            finally:
                stream.close()

            if self._cancelled or result is None:
                return

            if result.error:
                raise RuntimeError(f"Codex Agent error: {result.error}")

            self.signals.progress.emit("Synchronizing...")

            # Parse JSON từ response của Agent
            response_text = result.final_response or ""
            raw_paths = self._parse_agent_response(response_text)

            # Đọc settings để check excluded folders
            from domain.ports.registry import DomainRegistry

            settings = DomainRegistry.settings()
            excluded_patterns = [
                p.strip() for p in settings.excluded_folders.split("\n") if p.strip()
            ]

            # Thực hiện validate an toàn qua SelectionPathValidator
            from application.services.selection_path_validator import (
                validate_ai_selection,
            )

            validation = validate_ai_selection(
                workspace=self._workspace,
                raw_paths=raw_paths,
                ignore_patterns=excluded_patterns,
            )

            if validation.sensitive_blocked:
                logger.warning(
                    "Sensitive files blocked from selection: %s",
                    validation.sensitive_blocked,
                )

            if self._cancelled:
                return

            # Chỉ trả về các valid relative paths
            self.signals.finished.emit(validation.valid_paths)

        except Exception as e:
            logger.exception("Error in AIPickFilesWorker execution")
            self.signals.error.emit(str(e))
        finally:
            # Khôi phục lại biến môi trường ban đầu
            if old_env_key is None:
                os.environ.pop("AI_API_KEY", None)
            else:
                os.environ["AI_API_KEY"] = old_env_key

            if codex is not None:
                try:
                    codex.close()
                except Exception:
                    logger.warning("Failed to close Codex client", exc_info=True)

    def _parse_agent_response(self, response_text: str) -> List[str]:
        """
        Trích xuất danh sách đường dẫn từ response text của Agent một cách an toàn.
        """
        if not response_text:
            return []

        text = response_text.strip()

        # 1. Thử parse trực tiếp
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "paths" in data:
                return [p for p in data["paths"] if isinstance(p, str)]
            elif isinstance(data, list):
                return [p for p in data if isinstance(p, str)]
        except json.JSONDecodeError:
            pass

        # 2. Tìm khối code ```json ... ``` hoặc ``` ... ```
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            json_content = match.group(1)
            try:
                data = json.loads(json_content)
                if isinstance(data, dict) and "paths" in data:
                    return [p for p in data["paths"] if isinstance(p, str)]
                elif isinstance(data, list):
                    return [p for p in data if isinstance(p, str)]
            except json.JSONDecodeError:
                pass

        # 3. Fallback: tìm dấu ngoặc nhọn { đầu tiên và } cuối cùng
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_content = text[first_brace : last_brace + 1]
            try:
                data = json.loads(json_content)
                if isinstance(data, dict) and "paths" in data:
                    return [p for p in data["paths"] if isinstance(p, str)]
            except json.JSONDecodeError:
                pass

        # 4. Fallback 2: tìm dấu ngoặc vuông [ đầu tiên và ] cuối cùng
        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            json_content = text[first_bracket : last_bracket + 1]
            try:
                data = json.loads(json_content)
                if isinstance(data, list):
                    return [p for p in data if isinstance(p, str)]
            except json.JSONDecodeError:
                pass

        return []

    def _collect_stream_with_progress(self, stream, turn_id: str):
        """
        Duyệt stream sự kiện của Turn để phát hiện các MCP Tool Call, reasoning
        và phát ra tín hiệu progress, đồng thời tích luỹ TurnResult giống như _collect_turn_result.
        """
        from openai_codex.generated.v2_all import (
            ItemCompletedNotification,
            ThreadTokenUsageUpdatedNotification,
            TurnCompletedNotification,
            ItemStartedNotification,
        )
        from openai_codex._run import (
            _raise_for_failed_turn,
            _final_assistant_response_from_items,
            TurnResult,
        )

        completed = None
        items = []
        usage = None

        for event in stream:
            if self._cancelled:
                break

            payload = event.payload
            method = event.method

            # Gửi tín hiệu tiến độ dựa trên các sự kiện trong Agent Turn
            if (
                method == "item/started"
                and isinstance(payload, ItemStartedNotification)
                and payload.turn_id == turn_id
            ):
                item_root = getattr(payload.item, "root", None)
                if item_root:
                    item_type = getattr(item_root, "type", None)
                    if item_type == "mcpToolCall":
                        tool_name = getattr(item_root, "tool", "unknown")
                        self.signals.progress.emit(f"tool_call:{tool_name}")
                    elif item_type == "reasoning":
                        self.signals.progress.emit("reasoning")
                    elif item_type == "fileChange":
                        self.signals.progress.emit("file_change")

            if (
                isinstance(payload, ItemCompletedNotification)
                and payload.turn_id == turn_id
            ):
                items.append(payload.item)
                continue
            if (
                isinstance(payload, ThreadTokenUsageUpdatedNotification)
                and payload.turn_id == turn_id
            ):
                usage = payload.token_usage
                continue
            if (
                isinstance(payload, TurnCompletedNotification)
                and payload.turn.id == turn_id
            ):
                completed = payload

        if self._cancelled:
            return None

        if completed is None:
            raise RuntimeError("turn completed event not received")

        _raise_for_failed_turn(completed.turn)
        turn = completed.turn
        return TurnResult(
            id=turn.id,
            status=turn.status,
            error=turn.error,
            started_at=turn.started_at,
            completed_at=turn.completed_at,
            duration_ms=turn.duration_ms,
            final_response=_final_assistant_response_from_items(items),
            items=items,
            usage=usage,
        )
