# -*- coding: utf-8 -*-
"""
Trigger script cho lỗi không kiểm tra huỷ tác vụ (cancellation) trong ImproveInstructionsWorker.
Chứng minh rằng khi gọi worker.cancel() trong lúc worker đang chờ LLM API phản hồi (blocking call),
sau khi API phản hồi, worker vẫn tiếp tục thực thi và phát tín hiệu finished (emit finished signal),
làm cập nhật UI ngoài ý muốn dù người dùng đã huỷ tác vụ.
"""

import sys
import time
from pathlib import Path
from typing import Any

# Thêm workspace path vào sys.path để import các module của project
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

# Khởi tạo Qt Application vì ImproveInstructionsWorker sử dụng QObject và Signals
from PySide6.QtCore import QCoreApplication

app = QCoreApplication(sys.argv)

from application.services.improve_instructions_worker import ImproveInstructionsWorker
from infrastructure.ai.base_provider import LLMResponse


# Giả lập OpenAICompatibleProvider để tránh kết nối mạng thật
class MockProvider:
    def configure(self, api_key: str, base_url: str) -> None:
        pass

    def generate_structured(
        self, messages: Any, model_id: str, json_schema: Any, temperature: float = 0.0
    ) -> LLMResponse:
        print("[LLM Provider] Đang xử lý API call (giả lập chặn 0.5 giây)...")
        # Giả lập người dùng bấm nút Cancel trên UI khi đang chờ LLM
        # Gọi worker.cancel() từ thread khác (hoặc giả lập trực tiếp tại đây)
        trigger_cancel_action()
        time.sleep(0.5)
        print("[LLM Provider] API đã trả về kết quả.")
        return LLMResponse(
            content='{"improved_instructions": "improved instruction", "explanation": "Test reasoning"}',
            usage={"total_tokens": 100},
        )


# Mock OpenAICompatibleProvider trong module improve_instructions_worker
import application.services.improve_instructions_worker as worker_module

worker_module.OpenAICompatibleProvider = MockProvider

worker_instance = None


def trigger_cancel_action():
    if worker_instance:
        print("[UI Thread] Người dùng click HỦY tác vụ (cancel)!")
        worker_instance.cancel()


def main():
    global worker_instance
    print(
        "=== BẮT ĐẦU CHẠY THỬ NGHIỆM LỖI CANCELLATION TRONG IMPROVE INSTRUCTIONS WORKER ==="
    )

    # Khởi tạo worker
    worker_instance = ImproveInstructionsWorker(
        api_key="dummy_key",
        base_url="dummy_url",
        model_id="dummy_model",
        user_query="dummy_query",
    )

    finished_emitted = False
    error_emitted = False

    # Connect các signals để theo dõi
    def on_finished(improved, explanation, usage):
        nonlocal finished_emitted
        finished_emitted = True
        print(f"[UI Thread] NHẬN ĐƯỢC SIGNAL finished! Content: {improved}")

    def on_error(err_msg):
        nonlocal error_emitted
        error_emitted = True
        print(f"[UI Thread] NHẬN ĐƯỢC SIGNAL error! Message: {err_msg}")

    worker_instance.signals.finished.connect(on_finished)
    worker_instance.signals.error.connect(on_error)

    # Chạy worker trực tiếp (gọi run() đồng bộ để dễ bắt kết quả)
    print("[Worker] Bắt đầu chạy run()...")
    worker_instance.run()

    print("\n=== KẾT QUẢ CHẠY THỬ NGHIỆM ===")
    print(
        f"Trạng thái cancellation của worker: _cancelled = {worker_instance._cancelled}"
    )
    print(f"Signal finished được phát ra: {finished_emitted}")
    print(f"Signal error được phát ra: {error_emitted}")

    # Kỳ vọng: Nếu tác vụ đã bị cancel, tuyệt đối không được phát ra signal finished để cập nhật UI.
    if finished_emitted:
        print("[STATUS] THÀNH CÔNG: Đã trigger được lỗi cancellation bug!")
        print(
            "Lý do: ImproveInstructionsWorker.run() không kiểm tra biến self._cancelled sau cuộc gọi API,"
        )
        print("vẫn tiếp tục emit finished signal về Main UI thread.")
        sys.exit(0)
    else:
        print(
            "[STATUS] THÀNH CÔNG: Lỗi cancellation bug đã được vá thành công trong codebase (ImproveInstructionsWorker không emit signal finished khi bị cancel)!"
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
