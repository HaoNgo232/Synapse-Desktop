# Changelog - 2026-03-02

## Tool Rename: read_file → read_file_range

### Reason
- **Conflict:** Cursor has built-in `read_file` tool
- **Problem:** Name collision → MCP tool shadowed by built-in
- **Solution:** Rename to highlight unique feature (line range support)

### Changes
- ✅ Tool name: `read_file` → `read_file_range`
- ✅ System prompt updated
- ✅ README.md updated
- ✅ Docstring clarified

### Usage

**Cursor Built-in (simple reads):**
```python
read_file("src/main.py")  # Full file, fast
```

**Synapse MCP (line range):**
```python
read_file_range(workspace, "src/main.py", 
                start_line=100, end_line=150)
# Read specific lines, saves tokens
```

### Impact
- ✅ No more name collision
- ✅ Clear when to use which tool
- ✅ Highlights Synapse's unique feature

---

## System Prompt Optimization

### Changes
- **Before:** ~600 tokens (verbose tool list)
- **After:** ~200 tokens (workflow patterns)
- **Savings:** 66% reduction (400 tokens/request)

### Rationale
- Tool descriptions already in docstrings (no duplication)
- Focus on workflow patterns vs tool list
- Easier to maintain

### Impact
- ✅ 400 tokens saved per request
- ✅ More actionable guidance
- ✅ Better token management

---

## Bug Fixes
- Fixed regex syntax error in `_STRING_LITERAL_RE`

---

## Summary
- **Total tools:** 15/15 (100%)
- **Tool renamed:** 1 (read_file → read_file_range)
- **Prompt optimized:** 66% reduction
- **Status:** ✅ Production ready
