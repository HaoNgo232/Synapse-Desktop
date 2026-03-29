from domain.prompt.opx_parser import parse_opx_response


class TestOPXParserBugs:
    """
    Test suite to verify fixes for identified bugs in opx_parser.py.
    Dua tren report review:
    - Bug 1: re.sub global lam corrupt code content (HTML/XML tags)
    - Bug 2: Duplicate FileActions do regex overlap (self-closing vs paired)
    - Bug 3: Silent empty content khi thieu markers (parse error bi nuot)
    """

    def test_bug_1_content_corruption_html_fix(self):
        """
        Verify Bug 1 fix: '>' tiep giap line break không bi bien thanh '>>>'.
        """
        xml = """
<edit file="template.html" op="patch">
  <find>
<<<
<div
  class="old"
>
  <span>text</span>
</div>
>>>
  </find>
  <put>
<<<
<div
  class="new"
>
  <span>updated</span>
</div>
>>>
  </put>
</edit>
"""
        result = parse_opx_response(xml)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1
        action = result.file_actions[0]

        search_content = action.changes[0].search or ""
        put_content = action.changes[0].content or ""

        # FIX EXPECTATION: '>' should NOT be converted to '>>>'
        assert ">>>" not in search_content, (
            f"Bug 1: '>' was corrupted to '>>>' in search_content. Got:\n{search_content}"
        )
        assert ">>>" not in put_content, (
            f"Bug 1: '>' was corrupted to '>>>' in put_content. Got:\n{put_content}"
        )

        # Verify correct content preservation
        assert 'class="old"\n>\n  <span>' in search_content
        assert 'class="new"\n>\n  <span>' in put_content

    def test_bug_2_duplicate_actions_fix(self):
        """
        Verify Bug 2 fix: <edit ... /> không bi match boi PAIRED_REGEX neu da la self-closing.
        """
        xml = """
<edit file="file1.txt" op="remove" />
<edit file="file2.txt" op="new">
  <put><<<content>>></put>
</edit>
"""
        result = parse_opx_response(xml)

        paths = [action.path for action in result.file_actions]
        print(f"\nDetected paths: {paths}")

        # FIX EXPECTATION: ['file1.txt', 'file2.txt']
        assert paths == ["file1.txt", "file2.txt"]
        assert result.file_actions[0].action == "delete"
        assert result.file_actions[1].action == "create"

    def test_bug_3_parse_error_reporting_fix(self):
        """
        Verify Bug 3 fix: Marker bi thieu phai bao loi parse thay vi tra ve content rỗng.
        """
        xml = """
<edit file="main.py" op="new">
  <put>
    No markers at all in this block.
  </put>
</edit>
"""
        result = parse_opx_response(xml)

        # FIX EXPECTATION: Phai co error thong bao thieu marker
        assert len(result.errors) > 0, (
            "Should have reported a parse error for missing markers"
        )
        assert any("Missing <<< >>>" in err for err in result.errors)
        # Khong nen co action create neu content bi loi
        assert len(result.file_actions) == 0

    def test_bug_3_patch_parse_error_reporting_fix(self):
        """
        Verify Bug 3 fix cho patch operation.
        """
        xml = """
<edit file="main.py" op="patch">
  <find><<<old_code>>></find>
  <put>new_code_without_markers</put>
</edit>
"""
        result = parse_opx_response(xml)

        assert len(result.errors) > 0
        assert any("Missing <<< >>>" in err for err in result.errors)
        assert len(result.file_actions) == 0
