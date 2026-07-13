import logging
from typing import TYPE_CHECKING

import pytest

from __PACKAGE__.application.use_cases import CreateItemCommand
from __PACKAGE__.bootstrap import memory_application, sqlite_application

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
def test_sqlite_slice_persists_across_lifecycles(tmp_path: Path) -> None:
    database = tmp_path / "items.db"

    with sqlite_application(database) as application:
        event = application.create_item(CreateItemCommand(name="Wired item"))
        assert event.item_id.value
        assert event.occurred_at.tzinfo is not None

    with sqlite_application(database) as application:
        assert [item.name.value for item in application.list_items()] == ["Wired item"]


@pytest.mark.integration
def test_created_event_reaches_the_audit_log(caplog: pytest.LogCaptureFixture) -> None:
    application = memory_application()

    with caplog.at_level(logging.INFO):
        _ = application.create_item(CreateItemCommand(name="Audited"))

    assert any("Audited" in message for message in caplog.messages)
