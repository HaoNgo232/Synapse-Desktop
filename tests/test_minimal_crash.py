from views.context_view_qt import ContextViewQt
from services.service_container import ServiceContainer


def test_minimal_context_view_creation(qtbot):
    container = ServiceContainer()
    view = ContextViewQt(
        lambda: None,
        prompt_builder=container.prompt_builder,
        clipboard_service=container.clipboard,
        ignore_engine=container.ignore_engine,
        tokenization_service=container.tokenization,
    )
    qtbot.addWidget(view)
    assert view is not None
