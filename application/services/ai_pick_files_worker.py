"""
AI Pick Files Worker - Background worker chạy Codex Agent để tự động hóa việc chọn file.

Sử dụng QRunnable + QThreadPool để tương tác với Codex SDK trên secondary thread.
"""

import os
import json
import logging
from pathlib import Path
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

        self.signals.progress.emit("Initializing Codex...")

        # Đảm bảo thư mục .synapse tồn tại
        synapse_dir = Path(self._workspace) / ".synapse"
        synapse_dir.mkdir(parents=True, exist_ok=True)
        selection_file = synapse_dir / "selection.json"

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

        # Thiết lập biến môi trường để Codex SDK sử dụng cho custom provider
        os.environ["AI_API_KEY"] = self._api_key

        codex = None
        try:
            if self._cancelled:
                return

            codex = Codex(config=config)

            if self._cancelled:
                return

            self.signals.progress.emit("Connecting to Agent...")

            # Khởi chạy thread trong workspace với sandbox write
            thread = codex.thread_start(
                cwd=self._workspace, sandbox=Sandbox.workspace_write
            )

            prompt = f"""You are a file selection assistant. Your task is to identify all files in this workspace that are relevant to the user instruction: '{self._user_instruction}'.

Please explore the workspace using directory listing, file viewing, or search tools to find relevant files.
Once you have identified the relevant files, write the list of relative file paths directly into the file '.synapse/selection.json' in the workspace.
The format must strictly follow SelectionState v2 JSON structure:
{{
  "version": 2,
  "paths": [
    "relative/path/to/file1.py",
    "relative/path/to/file2.py"
  ],
  "provenance": {{
    "relative/path/to/file1.py": "agent",
    "relative/path/to/file2.py": "agent"
  }}
}}
Make sure to only select files that actually exist in the workspace and are highly relevant. Do not include files in your ignore list if any.
Do not write anything else to .synapse/selection.json. It must be valid JSON only.
"""
            if self._cancelled:
                return

            self.signals.progress.emit("AI Selecting...")

            # Chạy agent turn (blocking call trên thread con)
            result = thread.run(prompt)

            if self._cancelled:
                return

            if result.error:
                raise RuntimeError(f"Codex Agent error: {result.error}")

            self.signals.progress.emit("Synchronizing...")

            # 5. Validation and fallback
            selected_paths: List[str] = []
            if not selection_file.exists():
                logger.warning(
                    "Agent did not create selection.json. Attempting to initialize fallback..."
                )
                empty_state = {"version": 2, "paths": [], "provenance": {}}
                with open(selection_file, "w", encoding="utf-8") as f:
                    json.dump(empty_state, f, indent=2)
            else:
                try:
                    with open(selection_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if isinstance(data, dict) and "paths" in data:
                        raw_paths = data["paths"]
                        if isinstance(raw_paths, list):
                            selected_paths = [
                                p for p in raw_paths if isinstance(p, str)
                            ]

                    # Chuẩn hóa lại định dạng SelectionState v2 nếu cần
                    provenance = {p: "agent" for p in selected_paths}
                    corrected_state = {
                        "version": 2,
                        "paths": selected_paths,
                        "provenance": provenance,
                    }
                    with open(selection_file, "w", encoding="utf-8") as f:
                        json.dump(corrected_state, f, indent=2)

                except Exception as e:
                    logger.warning(
                        f"Error validating selection.json: {e}. Writing fallback."
                    )
                    empty_state = {"version": 2, "paths": [], "provenance": {}}
                    with open(selection_file, "w", encoding="utf-8") as f:
                        json.dump(empty_state, f, indent=2)

            if self._cancelled:
                return

            self.signals.finished.emit(selected_paths)

        except Exception as e:
            logger.exception("Error in AIPickFilesWorker execution")
            self.signals.error.emit(str(e))
        finally:
            if codex is not None:
                codex.close()
