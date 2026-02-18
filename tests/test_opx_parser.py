"""
Unit tests cho OPX Parser

Test cac case:
- Parse op="new" (create file)
- Parse op="patch" (modify with search/replace)
- Parse op="replace" (rewrite file)
- Parse op="remove" (delete file)
- Parse op="move" (rename file)
- Handle malformed XML gracefully
- Auto-heal truncated <<< >>> markers
"""

import pytest
from core.opx_parser import parse_opx_response


class TestParseNewOperation:
    """Test op="new" (create file)"""

    def test_parse_simple_create(self):
        """Parse mot create operation don gian"""
        xml = """
        <edit file="src/utils/hello.py" op="new">
            <put>
<<<
def hello():
    return "Hello, World!"
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "src/utils/hello.py"
        assert action.action == "create"
        assert len(action.changes) == 1
        assert "def hello():" in action.changes[0].content

    def test_parse_create_with_why(self):
        """Parse create voi <why> description"""
        xml = """
        <edit file="README.md" op="new">
            <why>Create project readme</why>
            <put>
<<<
# My Project
This is a test.
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.changes[0].description == "Create project readme"


class TestParsePatchOperation:
    """Test op="patch" (modify file)"""

    def test_parse_simple_patch(self):
        """Parse mot patch operation don gian"""
        xml = """
        <edit file="src/app.py" op="patch">
            <find>
<<<
def old_function():
    pass
>>>
            </find>
            <put>
<<<
def new_function():
    return 42
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "src/app.py"
        assert action.action == "modify"
        assert len(action.changes) == 1
        assert action.changes[0].search == "def old_function():\n    pass"
        assert "def new_function():" in action.changes[0].content

    def test_parse_patch_with_occurrence_first(self):
        """Parse patch voi occurrence="first" """
        xml = """
        <edit file="main.py" op="patch">
            <find occurrence="first">
<<<
# TODO
>>>
            </find>
            <put>
<<<
# DONE
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.changes[0].occurrence == "first"

    def test_parse_patch_with_occurrence_last(self):
        """Parse patch voi occurrence="last" """
        xml = """
        <edit file="main.py" op="patch">
            <find occurrence="last">
<<<
print("hello")
>>>
            </find>
            <put>
<<<
print("goodbye")
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.changes[0].occurrence == "last"

    def test_parse_patch_with_occurrence_number(self):
        """Parse patch voi occurrence="2" (numeric)"""
        xml = """
        <edit file="main.py" op="patch">
            <find occurrence="2">
<<<
x = 1
>>>
            </find>
            <put>
<<<
x = 100
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.changes[0].occurrence == 2


class TestParseReplaceOperation:
    """Test op="replace" (rewrite file)"""

    def test_parse_replace(self):
        """Parse mot replace operation"""
        xml = """
        <edit file="config.json" op="replace">
            <put>
<<<
{
    "version": "2.0"
}
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.action == "rewrite"
        assert '"version": "2.0"' in action.changes[0].content


class TestParseRemoveOperation:
    """Test op="remove" (delete file)"""

    def test_parse_remove_self_closing(self):
        """Parse remove voi self-closing tag"""
        xml = '<edit file="old_file.txt" op="remove" />'

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.path == "old_file.txt"
        assert action.action == "delete"

    def test_parse_remove_with_body(self):
        """Parse remove voi empty body"""
        xml = '<edit file="legacy.py" op="remove"></edit>'

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.action == "delete"


class TestParseMoveOperation:
    """Test op="move" (rename file)"""

    def test_parse_move(self):
        """Parse mot move operation"""
        xml = """
        <edit file="old_name.py" op="move">
            <to file="new_name.py" />
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.path == "old_name.py"
        assert action.action == "rename"
        assert action.new_path == "new_name.py"


class TestMultiRootWorkspace:
    """Test multi-root workspace support"""

    def test_parse_with_root_attribute(self):
        """Parse edit voi root attribute cho multi-workspace"""
        xml = """
        <edit file="src/main.py" op="new" root="backend">
            <put>
<<<
print("backend")
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        action = result.file_actions[0]
        assert action.root == "backend"


class TestMultipleEdits:
    """Test parsing multiple edits"""

    def test_parse_multiple_edits_in_opx_container(self):
        """Parse nhieu edits trong <opx> container"""
        xml = """
        <opx>
            <edit file="file1.py" op="new">
                <put>
<<<
# file 1
>>>
                </put>
            </edit>
            <edit file="file2.py" op="remove" />
        </opx>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        assert len(result.file_actions) == 2
        assert result.file_actions[0].action == "create"
        assert result.file_actions[1].action == "delete"


class TestErrorHandling:
    """Test error handling"""

    def test_empty_input(self):
        """Empty input tra ve error"""
        result = parse_opx_response("")

        assert len(result.errors) == 1
        assert "Empty input" in result.errors[0]

    def test_no_edit_elements(self):
        """Khong co <edit> elements tra ve error"""
        result = parse_opx_response("<div>Not an edit</div>")

        assert len(result.errors) == 1
        assert "No <edit> elements found" in result.errors[0]

    def test_missing_file_attribute(self):
        """Thieu file attribute tra ve error"""
        xml = '<edit op="new"><put><<<content>>></put></edit>'

        result = parse_opx_response(xml)

        assert len(result.errors) == 1
        assert "missing required attribute" in result.errors[0].lower()

    def test_missing_op_attribute(self):
        """Thieu op attribute tra ve error"""
        xml = '<edit file="test.py"><put><<<content>>></put></edit>'

        result = parse_opx_response(xml)

        assert len(result.errors) == 1
        assert "missing required attribute" in result.errors[0].lower()

    def test_unknown_op(self):
        """Unknown op tra ve error"""
        xml = '<edit file="test.py" op="unknown"><put><<<x>>></put></edit>'

        result = parse_opx_response(xml)

        assert len(result.errors) == 1
        assert 'unknown op="unknown"' in result.errors[0]


class TestAutoHealMarkers:
    """Test auto-heal truncated markers"""

    def test_heal_single_less_than(self):
        """Auto-heal < thanh <<<"""
        xml = """
        <edit file="test.py" op="new">
            <put>
<
content here
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        # Should still parse successfully due to auto-heal
        assert len(result.errors) == 0
        assert "content here" in result.file_actions[0].changes[0].content

    def test_heal_double_less_than(self):
        """Auto-heal << thanh <<<"""
        xml = """
        <edit file="test.py" op="new">
            <put>
<<
more content
>>>
            </put>
        </edit>
        """

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        assert "more content" in result.file_actions[0].changes[0].content


class TestSanitization:
    """Test response sanitization"""

    def test_strip_code_fences(self):
        """Strip markdown code fences"""
        xml = """```xml
        <edit file="test.py" op="new">
            <put>
<<<
hello
>>>
            </put>
        </edit>
        ```"""

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

    def test_strip_preamble(self):
        """Strip chat preamble truoc <edit>"""
        xml = """Sure, here's the code:
        
        <edit file="test.py" op="new">
            <put>
<<<
code
>>>
            </put>
        </edit>"""

        result = parse_opx_response(xml)

        assert len(result.errors) == 0
        assert len(result.file_actions) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
