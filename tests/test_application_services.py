"""
Tests cho các dịch vụ ứng dụng: AIContextWorker, Workspace Config, và Contract Pack.
"""

import json
from pathlib import Path
from typing import Any
import pytest

from domain.ports.ai_port import LLMResponse
from domain.ports.registry import DomainRegistry
from domain.contracts.contract_pack import (
    ContractPack,
    load_contract_pack,
    save_contract_pack,
    locked_modify_contract_pack,
    build_contract_pack,
)
from application.services.improve_instructions_worker import (
    ImproveInstructionsWorker,
)
from application.services.workspace_config import (
    get_excluded_patterns,
    get_use_gitignore,
    get_use_relative_paths,
    add_excluded_patterns,
    remove_excluded_patterns,
    _excluded_notifier,
)
from domain.config.app_settings import AppSettings


# ===========================================================================
# Workspace Config Tests
# ===========================================================================


class DummySettingsService:
    """Mock SettingsService để trả về AppSettings điều khiển được."""

    def __init__(self) -> None:
        self._settings = AppSettings(
            excluded_folders="node_modules\ndist",
            use_gitignore=True,
            use_relative_paths=True,
        )

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: Any) -> None:
        setattr(self._settings, key, value)


@pytest.fixture
def mock_settings_service():
    """Fixture cung cấp mock settings service cho DomainRegistry."""
    old_service = None
    try:
        old_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass

    service = DummySettingsService()
    DomainRegistry.register_settings_service(service)
    yield service

    # Restore old service
    if old_service is not None:
        DomainRegistry.register_settings_service(old_service)


def test_workspace_config_getters(mock_settings_service):
    """Test các hàm lấy cấu hình từ settings."""
    assert get_excluded_patterns() == ["node_modules", "dist"]
    assert get_use_gitignore() is True
    assert get_use_relative_paths() is True


def test_workspace_config_add_remove(mock_settings_service):
    """Test thêm và xóa excluded patterns."""
    called = False

    def on_change():
        nonlocal called
        called = True

    # Register notifier callback
    _excluded_notifier.connect(on_change)

    # Add pattern
    assert add_excluded_patterns(["build", "dist"]) is True
    assert get_excluded_patterns() == ["node_modules", "dist", "build"]
    assert called is True

    # Remove pattern
    called = False
    assert remove_excluded_patterns(["dist"]) is True
    assert get_excluded_patterns() == ["node_modules", "build"]
    assert called is True

    _excluded_notifier.disconnect(on_change)


# ===========================================================================
# Contract Pack Tests
# ===========================================================================


def test_contract_pack_dataclass():
    """Test properties, to_dict, from_dict và format_for_prompt của ContractPack."""
    pack = ContractPack(
        conventions=["Con 1"],
        anti_patterns=["Anti 1"],
        co_change_groups=[["a.py", "b.py"]],
        review_checklist=["Check 1"],
        required_tests=["test_a.py"],
        guarded_paths=["secrets/"],
    )

    # to_dict / from_dict
    d = pack.to_dict()
    restored = ContractPack.from_dict(d)
    assert restored.conventions == ["Con 1"]
    assert restored.anti_patterns == ["Anti 1"]
    assert restored.co_change_groups == [["a.py", "b.py"]]
    assert restored.review_checklist == ["Check 1"]
    assert restored.required_tests == ["test_a.py"]
    assert restored.guarded_paths == ["secrets/"]

    # format_for_prompt
    prompt = pack.format_for_prompt()
    assert "<conventions>" in prompt
    assert "- Con 1" in prompt
    assert "<anti_patterns>" in prompt
    assert "- ⚠️ Anti 1" in prompt
    assert "<co_change_groups>" in prompt
    assert "- a.py + b.py" in prompt
    assert "<review_checklist>" in prompt
    assert "- [ ] Check 1" in prompt
    assert "<guarded_paths>" in prompt
    assert "- 🔒 secrets/" in prompt


def test_contract_pack_save_load(tmp_path: Path):
    """Test load, save và locked modify contract pack."""
    # load từ file chưa tồn tại -> empty
    pack = load_contract_pack(tmp_path)
    assert len(pack.conventions) == 0

    # save
    pack.conventions.append("New Conv")
    save_contract_pack(tmp_path, pack)

    # load lại
    loaded = load_contract_pack(tmp_path)
    assert loaded.conventions == ["New Conv"]

    # locked modify
    def modifier(p: ContractPack) -> ContractPack:
        p.conventions.append("Mod Conv")
        return p

    locked_modify_contract_pack(tmp_path, modifier)

    loaded_mod = load_contract_pack(tmp_path)
    assert loaded_mod.conventions == ["New Conv", "Mod Conv"]


def test_build_contract_pack(tmp_path: Path):
    """Test build_contract_pack kết hợp các nguồn thông tin."""
    pack = build_contract_pack(
        workspace_root=tmp_path,
        workspace_rules_content="Rule 1\nRule 2",
        error_patterns=["Error 1"],
        co_change_hints=[["x.py", "y.py"]],
    )

    assert "Rule 1" in pack.conventions
    assert "Error 1" in pack.anti_patterns
    assert ["x.py", "y.py"] in pack.co_change_groups


# ===========================================================================
# ===========================================================================
# Improve Instructions Worker Tests
# ===========================================================================


class DummyAIProvider:
    """Mock AI Provider trả về response cấu trúc định sẵn."""

    def __init__(self) -> None:
        self.api_key = ""
        self.base_url = ""
        self.structured_response = LLMResponse(
            content=json.dumps(
                {
                    "improved_instructions": "improved instructions",
                    "explanation": "Core files for execution",
                }
            ),
            usage={"total_tokens": 150},
        )

    def configure(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url

    def generate_structured(
        self, messages, model_id, json_schema, temperature=0.0
    ) -> LLMResponse:
        return self.structured_response


def test_improve_instructions_worker_success(tmp_path: Path):
    """Test ImproveInstructionsWorker chạy thành công phát ra tín hiệu finished."""
    # Mock AI provider factory
    provider = DummyAIProvider()

    old_factory = None
    try:
        old_factory = DomainRegistry.ai_provider_factory()
    except RuntimeError:
        pass

    DomainRegistry.register_ai_provider_factory(lambda: provider)

    worker = ImproveInstructionsWorker(
        api_key="fake_key",
        base_url="fake_url",
        model_id="gpt-4",
        user_query="Run model",
        file_tree="root\n- main.py",
        git_diff="some diff",
    )

    # Listen to signals
    finished_called = False
    result_improved = ""
    result_explanation = ""
    result_usage = {}

    def on_finished(improved, explanation, usage):
        nonlocal finished_called, result_improved, result_explanation, result_usage
        finished_called = True
        result_improved = improved
        result_explanation = explanation
        result_usage = usage

    worker.signals.finished.connect(on_finished)

    # Chạy worker đồng bộ trong test thread
    worker.run()

    assert finished_called is True
    assert result_improved == "improved instructions"
    assert result_explanation == "Core files for execution"
    assert result_usage == {"total_tokens": 150}

    # Dọn dẹp
    if old_factory is not None:
        DomainRegistry.register_ai_provider_factory(old_factory)


def test_improve_instructions_worker_cancelled(tmp_path: Path):
    """Test ImproveInstructionsWorker bị cancel trước khi hoàn thành."""
    worker = ImproveInstructionsWorker(
        api_key="fake_key",
        base_url="fake_url",
        model_id="gpt-4",
        user_query="Query",
    )

    finished_called = False
    worker.signals.finished.connect(
        lambda imp, exp, u: setattr(finished_called, "val", True)
    )

    # Cancel worker
    worker.cancel()
    worker.run()

    assert finished_called is False
