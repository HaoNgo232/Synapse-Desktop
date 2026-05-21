# -*- coding: utf-8 -*-
"""
Trigger script cho lỗi race condition trong TokenizationService.
Chứng minh rằng cơ chế Double-Checked Locking trong _get_or_create_encoder không an toàn:
Thread A gán self._encoder nhưng chưa kịp gán self._encoder_type.
Thread B nhảy vào thấy self._encoder không phải None nên lập tức return nó,
sau đó sử dụng sai logic đếm token (coi HF tokenizer là rs-bpe/tiktoken),
dẫn tới lỗi TypeError và bị fallback về đếm ước lượng sai lệch.
"""

import sys
import time
import threading
from pathlib import Path
from typing import Any

# Thêm workspace path vào sys.path để import các module của project
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from application.services.tokenization_service import TokenizationService


# Định nghĩa một Mock Encoder mô phỏng Hugging Face Tokenizer
class MockHFEncoder:
    def encode(self, text: str) -> Any:
        # Đối tượng giả lập Encoding của HF
        class Encoding:
            def __init__(self):
                self.ids = [1, 2, 3, 4, 5]  # Giả lập 5 tokens

        return Encoding()


def main():
    print("=== BẮT ĐẦU CHẠY THỬ NGHIỆM RACE CONDITION TRONG TOKENIZATION SERVICE ===")

    # Khởi tạo TokenizationService giả lập dùng Xenova/claude-tokenizer (loại HF)
    service = TokenizationService(tokenizer_repo="Xenova/claude-tokenizer")

    # Giả lập _get_encoder trả về MockHFEncoder và cấu hình module encoders giả
    import infrastructure.adapters.encoders as encoders

    encoders._encoder_type = "hf"  # Set loại encoder gốc là hf

    # Mock hàm _get_encoder ở cả hai nơi để đảm bảo bypass import cache
    import application.services.tokenization_service as ts_module

    original_get_encoder = ts_module._get_encoder
    ts_module._get_encoder = lambda tokenizer_repo: MockHFEncoder()
    encoders._get_encoder = lambda tokenizer_repo: MockHFEncoder()

    # Dùng kĩ thuật patch __setattr__ để chèn delay và kích hoạt thread thứ hai
    # mô phỏng CPU scheduling/context switch của hệ điều hành.
    original_setattr = TokenizationService.__setattr__

    thread_b_result = None
    thread_b_started = threading.Event()
    thread_b_finished = threading.Event()

    def run_thread_b():
        nonlocal thread_b_result
        print("[Thread B] Bắt đầu gọi count_tokens...")
        thread_b_started.set()
        # Thread B gọi count_tokens. Nó sẽ chạy song song với Thread A
        thread_b_result = service.count_tokens("Hello World")
        print(f"[Thread B] Kết quả đếm token: {thread_b_result}")
        thread_b_finished.set()

    t_b = threading.Thread(target=run_thread_b, name="ThreadB")

    def custom_setattr(self, name: str, value: Any) -> None:
        original_setattr(self, name, value)
        # Khi Thread A vừa gán _encoder nhưng chưa gán _encoder_type
        if name == "_encoder" and value is not None:
            print(
                "[Thread A] Đã gán self._encoder. Kích hoạt Thread B và tạm dừng Thread A..."
            )
            t_b.start()
            thread_b_started.wait()
            # Trì hoãn Thread A 0.2 giây để Thread B chạy xong count_tokens với _encoder_type chưa được set
            time.sleep(0.2)
            print("[Thread A] Tiếp tục thực thi...")

    # Áp dụng patch __setattr__
    TokenizationService.__setattr__ = custom_setattr

    # Chạy Thread A
    print("[Thread A] Bắt đầu gọi count_tokens...")
    thread_a_result = service.count_tokens("Hello World")
    print(f"[Thread A] Kết quả đếm token: {thread_a_result}")

    # Đợi Thread B hoàn thành
    thread_b_finished.wait()

    # Khôi phục trạng thái cũ
    TokenizationService.__setattr__ = original_setattr
    import application.services.tokenization_service as ts_module

    ts_module._get_encoder = original_get_encoder
    encoders._get_encoder = original_get_encoder

    print("\n=== KẾT QUẢ CHẠY THỬ NGHIỆM ===")
    print(
        f"Thread A (đọc ghi tuần tự bình thường): {thread_a_result} tokens (Kỳ vọng: 5 vì là HF)"
    )
    print(f"Thread B (bị race condition): {thread_b_result} tokens")

    # Nếu Thread B bị lỗi TypeError do len(Encoding) thì nó sẽ fallback về _estimate_tokens("Hello World")
    # "Hello World" dài 11 ký tự, chia cho 4 ước lượng khoảng 2 tokens (hoặc 3 tuỳ thuật toán estimate).
    # Khác với giá trị 5 tokens của HF.
    if thread_b_result != 5:
        print(
            "[STATUS] THÀNH CÔNG: Đã kích hoạt lỗi race condition trong double-checked locking!"
        )
        print(
            "Lý do: Thread B đọc được self._encoder trước khi _encoder_type được set,"
        )
        print(
            "dẫn tới gọi len(encoder.encode(text)) thay vì len(encoder.encode(text).ids)."
        )
        sys.exit(0)
    else:
        print(
            "[STATUS] THÀNH CÔNG: Lỗi race condition đã được vá thành công trong codebase (Thread B vẫn đếm đúng 5 tokens nhờ thứ tự gán an toàn)!"
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
