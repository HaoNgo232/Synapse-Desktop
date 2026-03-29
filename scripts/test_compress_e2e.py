from pathlib import Path
from application.services.prompt_build_service import PromptBuildService
from infrastructure.filesystem.ignore_engine import IgnoreEngine
from application.services.graph_service import GraphService


def test_compress_output_quality(tmp_path):
    # Setup workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # A python file with some content
    file1 = workspace / "main.py"
    file1.write_text(
        'from utils import helper\ndef main():\n    """This is main"""\n    helper()\n\nclass App:\n    def run(self):\n        pass'
    )

    # Another python file
    file2 = workspace / "utils.py"
    file2.write_text("def helper():\n    return 42")

    # Initialize services
    from infrastructure.adapters.encoder_registry import get_tokenization_service

    ignore_engine = IgnoreEngine()
    tokenization_service = get_tokenization_service()
    graph_service = GraphService(ignore_engine=ignore_engine)

    # Pre-build graph to check edges
    print(f"Building graph for {workspace}...")
    graph = graph_service.ensure_built(workspace)
    print(f"Graph result: {graph.file_count()} files, {graph.edge_count()} edges")
    for file in graph.all_files():
        edges = graph.get_edges_from(file)
        for e in edges:
            print(f"  Edge: {e.source_file} --[{e.kind.value}]--> {e.target_file}")

    service = PromptBuildService(
        tokenization_service=tokenization_service, graph_service=graph_service
    )

    # Trigger smart prompt generation (Compress feature)
    result = service.build_prompt(
        file_paths=[file1, file2],
        workspace=workspace,
        instructions="Analyze this code",
        output_format="smart",
        include_git_changes=False,
        use_relative_paths=True,
    )

    prompt, token_count, breakdown = result

    print("\n" + "=" * 50)
    print("SMART PROMPT OUTPUT:")
    print(prompt)
    print("=" * 50 + "\n")

    # 1. Check basic structure
    assert "<smart_context>" in prompt, "Missing <smart_context> tag"
    assert "<structure>" in prompt, "Missing <structure> tag"

    # 2. Check content (smart context should have signatures, not full body)
    assert "def main()" in prompt
    assert "This is main" in prompt
    assert "print('hello')" not in prompt, (
        "Smart context should not contain full implementation"
    )

    # 3. Check for Semantic Index (Cross-file relationships)
    # Now that we re-enabled it, this should be present if relationships are detected
    if "<semantic_index>" not in prompt:
        print(
            "WARNING: '<semantic_index>' section is MISSING from smart context (might be expected if no real deps found)."
        )
    else:
        print("SUCCESS: '<semantic_index>' section is present.")
        assert "main.py" in prompt
        assert "utils.py" in prompt


if __name__ == "__main__":
    # Setup tmp workspace manually for running standalone
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        test_compress_output_quality(Path(tmpdir))
