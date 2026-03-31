from domain.codemap.symbol_extractor import extract_symbols
from domain.codemap.types import SymbolKind


def test_go_symbol_extraction_query_based():
    """
    Test Case này được thiết kế để THẤT BẠI (RED) trong giai đoạn TDD đầu tiên.
    Nó mong đợi trích xuất được symbols từ Go code, thứ mà Synapse chưa hỗ trợ cứng.
    Sau khi Refactor sang Query-based (SCM), test này phải PASS.
    """
    go_code = """
    package main
    import "fmt"
    
    // HelloWorld in Go
    func HelloWorld(name string) {
        fmt.Println("Hello", name)
    }
    
    type User struct {
        Name string
    }
    """
    # Hiện tại extract_symbols cho .go sẽ trả về [] vì chưa có logic node types cho Go
    symbols = extract_symbols("test.go", go_code)

    # Mong đợi tìm thấy function và struct thông qua Generic Query
    assert any(
        s.name == "HelloWorld" and s.kind == SymbolKind.FUNCTION for s in symbols
    )
    assert any(s.name == "User" and s.kind == SymbolKind.STRUCT for s in symbols)
    assert "HelloWorld in Go" in (
        next(s.signature for s in symbols if s.name == "HelloWorld") or ""
    )


def test_typescript_jsdoc_full_extraction():
    """Kiểm tra xem JSDoc đầy đủ có được trích xuất qua Query-based logic không."""
    ts_code = """
    /**
     * Tinh tong hai so.
     * @param a So thu nhat
     * @param b So thu hai
     */
    function add(a: number, b: number) {
        return a + b;
    }
    """
    # Test này kiểm chứng sự 'ngang tài ngang sức' giữa các ngôn ngữ qua SCM
    symbols = extract_symbols("math.ts", ts_code)
    func_symbol = next(s for s in symbols if s.name == "add")
    assert "Tinh tong hai so." in (func_symbol.signature or "")
    assert "@param a" in (func_symbol.signature or "")
