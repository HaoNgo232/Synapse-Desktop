"""
Tests cho nâng cấp token counter hiện có.

Các test tập trung vào TokenUsageBar đang render token counter trong Context tab.
"""

import sys
import types
from dataclasses import dataclass
from unittest.mock import MagicMock

from PySide6.QtWidgets import QLabel

from domain.tokenization.comparison_service import TokenComparison
from presentation.components.token_usage_bar import TokenUsageBar
from presentation.config.theme import ThemeColors


@dataclass
class _FakeModel:
    file_count: int

    def get_selected_file_count(self) -> int:
        return self.file_count


class _FakeFileTree:
    def __init__(self, paths: list[str], total_tokens: int):
        self._paths = paths
        self._total_tokens = total_tokens
        self._model = _FakeModel(file_count=len(paths))

    def get_model(self) -> _FakeModel:
        return self._model

    def get_total_tokens(self) -> int:
        return self._total_tokens

    def get_selected_paths(self) -> list[str]:
        return self._paths


class _FakeTextEdit:
    def toPlainText(self) -> str:
        return ""


class _FakeComparisonService:
    def __init__(self, result: TokenComparison):
        self.result = result
        self.calls: list[list[str]] = []

    def compare_paths(self, file_paths: list[str]) -> TokenComparison:
        self.calls.append(file_paths)
        return self.result


def _label_texts(widget: TokenUsageBar) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def test_smart_line_hidden_when_no_selection(qtbot):
    widget = TokenUsageBar()
    qtbot.addWidget(widget)

    widget.update_stats(tokens=0, limit=200000, files=0)

    text = " ".join(_label_texts(widget))
    assert "Full: 0" in text
    assert "Smart:" not in text


def test_smart_line_visible_when_files_selected(qtbot):
    widget = TokenUsageBar()
    qtbot.addWidget(widget)

    widget.update_stats(
        tokens=48200,
        limit=200000,
        files=2,
        smart_tokens=8400,
        savings_pct=83.0,
    )

    text = " ".join(_label_texts(widget))
    assert "Full: 48,200" in text
    assert "Smart: 8,400" in text
    assert "83%" in text


def test_savings_color_green_when_gte_30pct(qtbot):
    widget = TokenUsageBar()
    qtbot.addWidget(widget)

    widget.update_stats(
        tokens=48200,
        limit=200000,
        files=1,
        smart_tokens=8400,
        savings_pct=83.0,
    )

    assert ThemeColors.SUCCESS in widget._smart_label.styleSheet()


def test_savings_color_gray_when_lt_30pct(qtbot):
    widget = TokenUsageBar()
    qtbot.addWidget(widget)

    widget.update_stats(
        tokens=10000,
        limit=200000,
        files=1,
        smart_tokens=8000,
        savings_pct=20.0,
    )

    assert ThemeColors.TEXT_MUTED in widget._smart_label.styleSheet()


def test_smart_line_hidden_when_savings_lt_1pct(qtbot):
    widget = TokenUsageBar()
    qtbot.addWidget(widget)

    widget.update_stats(
        tokens=10000,
        limit=200000,
        files=1,
        smart_tokens=9950,
        savings_pct=0.5,
    )

    text = " ".join(_label_texts(widget))
    assert "Full: 10,000" in text
    assert "Smart:" not in text


def test_no_duplicate_token_counter_in_layout(qtbot):
    widget = TokenUsageBar()
    qtbot.addWidget(widget)

    full_labels = widget.findChildren(QLabel, "tokenUsageFullLabel")
    smart_labels = widget.findChildren(QLabel, "tokenUsageSmartLabel")

    assert len(full_labels) == 1
    assert len(smart_labels) == 1


def test_update_triggered_same_time_as_existing_counter(qtbot, monkeypatch):
    ui_builder = types.ModuleType("presentation.views.context.ui_builder")
    ui_builder.UIBuilderMixin = object
    monkeypatch.setitem(
        sys.modules,
        "presentation.views.context.ui_builder",
        ui_builder,
    )

    from presentation.views.context.context_view_qt import ContextViewQt

    bar = TokenUsageBar()
    qtbot.addWidget(bar)

    comparison_service = _FakeComparisonService(
        TokenComparison(
            full_tokens=48200,
            smart_tokens=8400,
            tree_map_tokens=120,
            savings_pct=83.0,
        )
    )

    def run_immediately(
        fn, on_result=None, on_error=None, on_finished=None, *args, **kwargs
    ):
        result = fn(*args, **kwargs)
        if on_result:
            on_result(result)
        if on_finished:
            on_finished()
        return MagicMock()

    monkeypatch.setattr(
        "presentation.utils.qt_utils.schedule_background",
        run_immediately,
    )

    view = ContextViewQt.__new__(ContextViewQt)
    view.file_tree_widget = _FakeFileTree(["/project/a.py"], 48200)
    view._instructions_field = _FakeTextEdit()
    view._prompt_builder = MagicMock()
    view._prompt_builder.count_tokens.return_value = 0
    view._token_usage_bar = bar
    view._selected_model_id = "claude-3-5-sonnet"
    view._token_comparison_service = comparison_service
    view._smart_comparison_generation = 0
    view._smart_comparison_worker = None

    ContextViewQt._update_token_display(view)
    view._on_comparison_debounce_timeout()

    assert comparison_service.calls == [["/project/a.py"]]
    assert "Full: 48,200" in bar._token_label.text()
    assert "Smart: 8,400" in bar._smart_label.text()
