from typing import Any, Dict, List
from domain.prompt.opx_parser import parse_opx_response


class TestOPXParserStress:
    """
    Stress test for OPX Parser covering 100+ use cases and diverse content.
    """

    def test_diverse_contents_stress(self):
        cases: List[Dict[str, Any]] = []

        # 1-10: Basic valid cases
        for i in range(1, 11):
            cases.append(
                {
                    "name": f"Basic New File {i}",
                    "xml": f'<edit file="file{i}.txt" op="new"><put><<<Content {i}>>></put></edit>',
                    "expected_actions": 1,
                    "expected_path": f"file{i}.txt",
                    "expected_content": f"Content {i}",
                }
            )

        # 11-20: HTML/XML Bug 1 edge cases (lone > and <)
        html_content = '<div class="test">\n  >\n  <span>\n    <\n  </span>\n</div>'
        for i in range(11, 21):
            cases.append(
                {
                    "name": f"HTML Content with lone brackets {i}",
                    "xml": f'<edit file="index{i}.html" op="new"><put><<<\n{html_content}\n>>></put></edit>',
                    "expected_actions": 1,
                    "expected_content_contains": [">", "<", 'class="test"'],
                    "forbidden_content_contains": [">>>", "<<<"],
                }
            )

        # 21-30: Bug 2 edge cases (Mix of self-closing and paired)
        for i in range(21, 31):
            cases.append(
                {
                    "name": f"Mixed Edits {i}",
                    "xml": f"""
<edit file="del{i}.txt" op="remove" />
<edit file="patch{i}.py" op="patch">
  <find><<<old>>></find>
  <put><<<new>>></put>
</edit>
<edit file="new{i}.js" op="new"><put><<<console.log('test')>>></put></edit>
""",
                    "expected_actions": 3,
                    "expected_paths": [f"del{i}.txt", f"patch{i}.py", f"new{i}.js"],
                }
            )

        # 31-40: Python Bitshifts (Ensure no false positives for auto-heal)
        python_code = "x = a << 5\ny = b >> 2\nif x < y:\n    print('less')"
        for i in range(31, 41):
            cases.append(
                {
                    "name": f"Python Bitshifts {i}",
                    "xml": f'<edit file="math{i}.py" op="new"><put><<<\n{python_code}\n>>></put></edit>',
                    "expected_actions": 1,
                    "expected_content": python_code,
                }
            )

        # 41-50: Unicode and Special Characters
        unicode_str = "Xin chào các bạn! 🍎 🚀 Vietnamese: Tiếng Việt có dấu."
        for i in range(41, 51):
            cases.append(
                {
                    "name": f"Unicode Stress {i}",
                    "xml": f'<edit file="lang{i}.txt" op="new"><put><<<{unicode_str}>>></put></edit>',
                    "expected_actions": 1,
                    "expected_content": unicode_str,
                }
            )

        # 51-60: Bug 3 trigger (Malformed/Missing Markers)
        for i in range(51, 61):
            cases.append(
                {
                    "name": f"Missing Markers Error {i}",
                    "xml": f'<edit file="error{i}.py" op="new"><put>Missing markers here</put></edit>',
                    "expected_errors": 1,
                }
            )

        # 61-70: Auto-heal truncated markers (Slow path)
        for i in range(61, 71):
            cases.append(
                {
                    "name": f"Truncated Markers Auto-heal {i}",
                    "xml": f'<edit file="heal{i}.txt" op="new"><put>\n<\nHealed content {i}\n>\n</put></edit>',
                    "expected_actions": 1,
                    "expected_content": f"Healed content {i}",
                }
            )

        # 71-80: Large whitespace preservation
        for i in range(71, 81):
            cases.append(
                {
                    "name": f"Whitespace Preservation {i}",
                    "xml": f'<edit file="space{i}.txt" op="new"><put><<<\n    Line 1\n\n    Line 3    \n>>></put></edit>',
                    "expected_actions": 1,
                    "expected_content": "Line 1\n\n    Line 3",
                }
            )

        # 81-90: Multiple Changes in one Edit (Only the first one is processed by current implementation)
        for i in range(81, 91):
            cases.append(
                {
                    "name": f"Multiple Put/Find {i}",
                    "xml": f'<edit file="multi{i}.py" op="patch"><find><<<f>>></find><put><<<p>>></put><find><<<f2>>></find><put><<<p2>>></put></edit>',
                    "expected_actions": 1,
                    "expected_changes": 1,
                }
            )

        # 91-100: JSON content
        json_content = '{\n  "key": "value",\n  "array": [1, 2, 3]\n}'
        for i in range(91, 101):
            cases.append(
                {
                    "name": f"JSON Stress {i}",
                    "xml": f'<edit file="data{i}.json" op="new"><put><<<{json_content}>>></put></edit>',
                    "expected_actions": 1,
                    "expected_content": json_content,
                }
            )

        # Execute all 100 cases
        for case in cases:
            res = parse_opx_response(case["xml"])

            if "expected_errors" in case:
                assert len(res.errors) >= case["expected_errors"], (
                    f"Failed case '{case['name']}'"
                )
                continue

            assert not res.errors, f"Failed case '{case['name']}': {res.errors}"

            if "expected_actions" in case:
                assert len(res.file_actions) == case["expected_actions"]

            if "expected_path" in case:
                assert res.file_actions[0].path == case["expected_path"]

            if "expected_paths" in case:
                found_paths = [a.path for a in res.file_actions]
                assert found_paths == case.get("expected_paths")

            if "expected_content" in case:
                assert res.file_actions[0].changes[0].content == case.get(
                    "expected_content"
                )

            expected_contains = case.get("expected_content_contains")
            if isinstance(expected_contains, list):
                content = res.file_actions[0].changes[0].content
                for item in expected_contains:
                    assert item in content

            forbidden_contains = case.get("forbidden_content_contains")
            if isinstance(forbidden_contains, list):
                content = res.file_actions[0].changes[0].content
                for item in forbidden_contains:
                    assert item not in content

            if "expected_changes" in case:
                assert len(res.file_actions[0].changes) == case.get("expected_changes")

    def test_marker_overlap_ambiguity(self):
        """
        Verify that <<< and >>> inside code (not as lone markers) don't break extraction.
        """
        code = "print('DEBUG: <<< starting >>>')"
        xml = f'<edit file="ambiguous.py" op="new"><put><<<\n{code}\n>>></put></edit>'
        res = parse_opx_response(xml)
        assert not res.errors
        assert res.file_actions[0].changes[0].content == code
