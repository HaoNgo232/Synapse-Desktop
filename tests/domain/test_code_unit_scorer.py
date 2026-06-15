import unittest
from unittest.mock import MagicMock
from domain.workflow.shared.code_unit_scorer import (
    CodeUnit,
    score_code_unit,
    SCORE_BASE,
    SCORE_WEIGHTS,
    PENALTY_PER_THOUSAND_CHARS,
)


class TestCodeUnitScorer(unittest.TestCase):
    def test_code_unit_init(self):
        # Case estimated_tokens == 0 -> xấp xỉ bằng len(content) // 4
        unit1 = CodeUnit(
            name="test_func",
            kind="function",
            content="a" * 40,
            line_start=1,
            line_end=5,
        )
        self.assertEqual(unit1.estimated_tokens, 10)

        # content rất ngắn (dưới 4 ký tự) -> estimated_tokens tối thiểu là 1
        unit2 = CodeUnit(
            name="test_func", kind="function", content="a", line_start=1, line_end=2
        )
        self.assertEqual(unit2.estimated_tokens, 1)

        # Case estimated_tokens đã được truyền khác 0
        unit3 = CodeUnit(
            name="test_func",
            kind="function",
            content="a" * 40,
            line_start=1,
            line_end=5,
            estimated_tokens=15,
        )
        self.assertEqual(unit3.estimated_tokens, 15)

    def test_score_code_unit_base(self):
        # Base score = SCORE_BASE - len(content)/1000 * PENALTY
        content = "a" * 1000
        unit = CodeUnit(
            name="test_func",
            kind="function",
            content=content,
            line_start=1,
            line_end=5,
        )
        expected_score = SCORE_BASE - (
            1000 / 1000 * PENALTY_PER_THOUSAND_CHARS
        )  # 5.0 - 1.0 = 4.0
        self.assertEqual(score_code_unit(unit, None, None), expected_score)

    def test_score_code_unit_relevance_hints(self):
        unit = CodeUnit(
            name="target_func",
            kind="function",
            content="pass",
            line_start=1,
            line_end=2,
        )

        # Có match hints
        score_with_hint = score_code_unit(unit, None, {"target_func", "other_func"})
        base_score = SCORE_BASE - (4 / 1000 * PENALTY_PER_THOUSAND_CHARS)
        self.assertEqual(score_with_hint, base_score + SCORE_WEIGHTS["RELEVANCE_HINT"])

        # Không match hints
        score_without_hint = score_code_unit(unit, None, {"other_func"})
        self.assertEqual(score_without_hint, base_score)

    def test_score_code_unit_with_codemap_builder(self):
        unit = CodeUnit(
            name="my_func", kind="function", content="pass", line_start=1, line_end=2
        )

        mock_builder = MagicMock()
        mock_builder.get_callers.return_value = ["caller1", "caller2"]  # 2 * 3 = 6
        mock_builder.get_callees.return_value = ["callee1"]  # 1 * 1 = 1

        score = score_code_unit(unit, mock_builder, None)
        base_score = SCORE_BASE - (4 / 1000 * PENALTY_PER_THOUSAND_CHARS)
        expected_score = (
            base_score
            + (2 * SCORE_WEIGHTS["IN_DEGREE"])
            + (1 * SCORE_WEIGHTS["OUT_DEGREE"])
        )
        self.assertEqual(score, expected_score)

        mock_builder.get_callers.assert_called_once_with("my_func")
        mock_builder.get_callees.assert_called_once_with("my_func")

    def test_score_code_unit_main_boost(self):
        unit = CodeUnit(
            name="main", kind="function", content="pass", line_start=1, line_end=2
        )
        score = score_code_unit(unit, None, None)
        base_score = SCORE_BASE - (4 / 1000 * PENALTY_PER_THOUSAND_CHARS)
        self.assertEqual(score, base_score + SCORE_WEIGHTS["RELEVANCE_MAIN"])

    def test_score_code_unit_docs_boost(self):
        base_score = SCORE_BASE - (9 / 1000 * PENALTY_PER_THOUSAND_CHARS)

        # Python docstring triple double quotes
        unit1 = CodeUnit(
            name="func", kind="function", content='"""doc"""', line_start=1, line_end=2
        )
        self.assertEqual(
            score_code_unit(unit1, None, None),
            base_score + SCORE_WEIGHTS["RELEVANCE_DOCS"],
        )

        # Python docstring triple single quotes
        unit2 = CodeUnit(
            name="func", kind="function", content="'''doc'''", line_start=1, line_end=2
        )
        self.assertEqual(
            score_code_unit(unit2, None, None),
            base_score + SCORE_WEIGHTS["RELEVANCE_DOCS"],
        )

        # C-style docstring (///)
        unit3 = CodeUnit(
            name="func", kind="function", content="/// doc  ", line_start=1, line_end=2
        )
        self.assertEqual(
            score_code_unit(unit3, None, None),
            base_score + SCORE_WEIGHTS["RELEVANCE_DOCS"],
        )

        # Java-style docstring (/**)
        unit4 = CodeUnit(
            name="func", kind="function", content="/** doc  ", line_start=1, line_end=2
        )
        self.assertEqual(
            score_code_unit(unit4, None, None),
            base_score + SCORE_WEIGHTS["RELEVANCE_DOCS"],
        )


if __name__ == "__main__":
    unittest.main()
