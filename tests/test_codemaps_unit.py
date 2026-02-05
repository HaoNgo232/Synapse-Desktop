"""
Unit tests cho CodeMaps feature.

Chạy: pytest tests/test_codemaps_unit.py -v
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.smart_context.parser import smart_parse, _build_relationships_section
from core.codemaps.relationship_extractor import (
    extract_relationships,
    _build_function_boundaries_map,
    _find_enclosing_function_fast,
)
from core.codemaps.types import RelationshipKind
from core.smart_context.loader import get_language
from tree_sitter import Parser


# ============================================================
# Test Data
# ============================================================

SAMPLE_PYTHON_CODE = '''
def outer_function():
    """Outer function docstring."""
    helper()
    process_data()

def helper():
    """Helper function."""
    pass

class MyClass(BaseClass):
    """My class docstring."""
    
    def method(self):
        self.helper()
        other_function()
'''

SAMPLE_JS_CODE = '''
function fetchData() {
    const result = processResult();
    return result;
}

class Component extends React.Component {
    render() {
        return this.getData();
    }
}
'''


# ============================================================
# Test extract_relationships
# ============================================================

class TestExtractRelationships:
    """Tests for extract_relationships function."""
    
    def test_extract_function_calls_python(self):
        """Test extraction of function calls in Python."""
        relationships = extract_relationships("test.py", SAMPLE_PYTHON_CODE)
        
        calls = [r for r in relationships if r.kind == RelationshipKind.CALLS]
        assert len(calls) > 0, "Should extract at least one function call"
        
        # Check specific calls
        call_targets = [r.target for r in calls]
        assert "helper" in call_targets, "Should find helper() call"
        assert "process_data" in call_targets, "Should find process_data() call"
    
    def test_extract_class_inheritance_python(self):
        """Test extraction of class inheritance in Python."""
        relationships = extract_relationships("test.py", SAMPLE_PYTHON_CODE)
        
        inherits = [r for r in relationships if r.kind == RelationshipKind.INHERITS]
        assert len(inherits) > 0, "Should extract at least one inheritance"
        
        # Check MyClass inherits from BaseClass
        inheritance_pairs = [(r.source, r.target) for r in inherits]
        assert ("MyClass", "BaseClass") in inheritance_pairs
    
    def test_tree_reuse_optimization(self):
        """Test that tree reuse works correctly."""
        language = get_language("py")
        parser = Parser(language)
        tree = parser.parse(bytes(SAMPLE_PYTHON_CODE, "utf-8"))
        
        # Extract with pre-parsed tree
        relationships = extract_relationships(
            "test.py", SAMPLE_PYTHON_CODE, 
            tree=tree, language=language
        )
        
        assert len(relationships) > 0, "Should work with pre-parsed tree"
    
    def test_empty_content(self):
        """Test with empty content."""
        relationships = extract_relationships("test.py", "")
        assert relationships == []
    
    def test_unsupported_language(self):
        """Test with unsupported file extension."""
        relationships = extract_relationships("test.xyz", "some content")
        assert relationships == []


# ============================================================
# Test boundaries map optimization
# ============================================================

class TestBoundariesMapOptimization:
    """Tests for function boundaries map optimization."""
    
    def test_build_boundaries_map(self):
        """Test building function boundaries map."""
        language = get_language("py")
        parser = Parser(language)
        tree = parser.parse(bytes(SAMPLE_PYTHON_CODE, "utf-8"))
        lines = SAMPLE_PYTHON_CODE.split("\n")
        
        boundaries = _build_function_boundaries_map(tree.root_node, lines)
        
        assert len(boundaries) > 0, "Should find at least one function"
        
        # Check structure
        for start, end, name in boundaries:
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert isinstance(name, str)
            assert start <= end
    
    def test_find_enclosing_function_fast(self):
        """Test fast enclosing function lookup."""
        language = get_language("py")
        parser = Parser(language)
        tree = parser.parse(bytes(SAMPLE_PYTHON_CODE, "utf-8"))
        lines = SAMPLE_PYTHON_CODE.split("\n")
        
        boundaries = _build_function_boundaries_map(tree.root_node, lines)
        
        # Find a line inside outer_function (line 3 approx)
        result = _find_enclosing_function_fast(3, boundaries)
        assert result == "outer_function"
    
    def test_find_enclosing_function_none(self):
        """Test when line is outside all functions."""
        boundaries = [(10, 20, "func1"), (30, 40, "func2")]
        
        result = _find_enclosing_function_fast(5, boundaries)
        assert result is None


# ============================================================
# Test smart_parse integration
# ============================================================

class TestSmartParseIntegration:
    """Tests for smart_parse with relationships."""
    
    def test_smart_parse_without_relationships(self):
        """Test smart_parse without relationships (default)."""
        result = smart_parse("test.py", SAMPLE_PYTHON_CODE)
        
        assert result is not None
        assert "## Relationships" not in result
    
    def test_smart_parse_with_relationships(self):
        """Test smart_parse with relationships enabled."""
        result = smart_parse("test.py", SAMPLE_PYTHON_CODE, include_relationships=True)
        
        assert result is not None
        assert "## Relationships" in result
        assert "Function Calls" in result
    
    def test_backward_compatibility(self):
        """Test that default behavior is backward compatible."""
        # Without explicit parameter
        result1 = smart_parse("test.py", SAMPLE_PYTHON_CODE)
        
        # With explicit False
        result2 = smart_parse("test.py", SAMPLE_PYTHON_CODE, include_relationships=False)
        
        # Both should not have relationships
        assert "## Relationships" not in result1
        assert "## Relationships" not in result2


# ============================================================
# Test _build_relationships_section
# ============================================================

class TestBuildRelationshipsSection:
    """Tests for _build_relationships_section function."""
    
    def test_build_section_format(self):
        """Test output format of relationships section."""
        result = _build_relationships_section("test.py", SAMPLE_PYTHON_CODE)
        
        assert result is not None
        assert result.startswith("## Relationships")
        assert "###" in result  # Should have subsections
    
    def test_build_section_with_tree_reuse(self):
        """Test with pre-parsed tree (optimization)."""
        language = get_language("py")
        parser = Parser(language)
        tree = parser.parse(bytes(SAMPLE_PYTHON_CODE, "utf-8"))
        
        result = _build_relationships_section(
            "test.py", SAMPLE_PYTHON_CODE,
            tree=tree, language=language
        )
        
        assert result is not None
        assert "## Relationships" in result
    
    def test_build_section_empty_file(self):
        """Test with file that has no relationships."""
        result = _build_relationships_section("test.py", "x = 1\ny = 2\n")
        
        # Should return None or empty when no relationships
        assert result is None or "## Relationships" not in result


# ============================================================
# Run tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
