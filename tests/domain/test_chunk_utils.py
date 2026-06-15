import unittest
from domain.smart_context.chunk_utils import (
    filter_duplicated_chunks,
    merge_adjacent_chunks,
    check_and_add,
)


class TestChunkUtils(unittest.TestCase):
    def test_filter_duplicated_chunks(self):
        # Trường hợp bình thường
        chunks = [
            {"content": "short", "start_row": 1, "end_row": 5},
            {"content": "much longer content", "start_row": 1, "end_row": 10},
            {"content": "another", "start_row": 2, "end_row": 6},
        ]
        filtered = filter_duplicated_chunks(chunks)
        # Sắp xếp theo start_row: 1, 2
        # start_row=1 giữ chunk dài nhất là "much longer content"
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["content"], "much longer content")
        self.assertEqual(filtered[1]["content"], "another")

    def test_merge_adjacent_chunks(self):
        # 0 hoặc 1 chunk
        self.assertEqual(merge_adjacent_chunks([]), [])
        self.assertEqual(
            merge_adjacent_chunks([{"content": "a", "start_row": 1, "end_row": 2}]),
            [{"content": "a", "start_row": 1, "end_row": 2}],
        )

        # Chunks liền kề (previous end_row + 1 == current start_row)
        chunks = [
            {"content": "line 1", "start_row": 1, "end_row": 1},
            {"content": "line 2", "start_row": 2, "end_row": 2},
            {"content": "line 4", "start_row": 4, "end_row": 4},
        ]
        merged = merge_adjacent_chunks(chunks)
        self.assertEqual(len(merged), 2)
        # Chunk 1 và 2 gộp
        self.assertEqual(merged[0]["content"], "line 1\nline 2")
        self.assertEqual(merged[0]["start_row"], 1)
        self.assertEqual(merged[0]["end_row"], 2)
        # Chunk 3 không đổi
        self.assertEqual(merged[1]["content"], "line 4")
        self.assertEqual(merged[1]["start_row"], 4)
        self.assertEqual(merged[1]["end_row"], 4)

    def test_check_and_add(self):
        processed = set()

        # Thêm mới
        res1 = check_and_add("  hello  ", processed)
        self.assertEqual(res1, "hello")
        self.assertIn("hello", processed)

        # Thêm trùng lặp
        res2 = check_and_add("hello", processed)
        self.assertIsNone(res2)

        # Thêm trùng lặp có khoảng trắng
        res3 = check_and_add(" hello \n", processed)
        self.assertIsNone(res3)


if __name__ == "__main__":
    unittest.main()
