"""
E2E тесты подписок: импорт, обновление, удаление, отмена импорта.
"""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

from textual.widgets import DataTable, Input, TabbedContent

from tests.e2e.conftest import FAKE_SUBSCRIPTION_PAYLOAD, FakeService, make_test_app


async def test_import_subscription_modal(
    temp_store_dir: Path, project_root: Path
):
    """Открыть модал импорта, заполнить имя и URL, нажать Добавить,
    проверить что подписка появилась в #sub-table."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Switch to nodes tab
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Open import subscription modal
        await pilot.click("#btn-import-sub")
        await pilot.pause()

        # Fill the form — query modal widgets from the active screen
        modal = pilot.app.screen
        name_input = modal.query_one("#inp-sub-name", Input)
        name_input.value = "Test Subscription"
        url_input = modal.query_one("#inp-sub-url", Input)
        url_input.value = "https://example.com/sub"

        # Submit the modal
        await pilot.click("#btn-sub-add")
        await pilot.pause()
        await pilot.pause()  # wait for executor

        # Verify subscription appeared in the table
        sub_table = pilot.app.query_one("#sub-table", DataTable)
        assert sub_table.row_count == 1, (
            f"Expected 1 subscription, got {sub_table.row_count}"
        )
        row_values = sub_table.get_row_at(0)
        assert "Test Subscription" in row_values[0]


async def test_refresh_subscription(
    temp_store_dir: Path, project_root: Path
):
    """Добавить подписку, обновить её (кнопка #btn-refresh-sub),
    проверить что в #nodes-table появились узлы."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    # Pre-add a subscription so we can refresh it
    result = service.add_subscription("Refresh Test", "https://example.com/refresh")
    sub_id = result["subscription"]["id"]

    # Build fake base64-encoded payload (as real subscriptions provide)
    payload_b64 = base64.b64encode(FAKE_SUBSCRIPTION_PAYLOAD.encode()).decode()

    # Mock urllib.request.urlopen so subvost_store.refresh_subscription
    # gets our fake data instead of hitting the network.
    #
    # Critical: MagicMock.__enter__ returns a *new* mock by default, but the
    # store's refresh_subscription uses "with urlopen(...) as response:", so
    # we must wire __enter__ to return the same object carrying our read data,
    # status, and headers.
    fake_response = MagicMock()
    fake_response.read.return_value = payload_b64.encode("utf-8")
    fake_response.status = 200
    fake_response.headers = {"ETag": "", "Last-Modified": ""}
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response):
        async with make_test_app(service).run_test() as pilot:
            await pilot.pause()

            # Switch to nodes tab
            tabs = pilot.app.query_one(TabbedContent)
            tabs.active = "tab-nodes"
            await pilot.pause()

            # Select the subscription in sub-table
            sub_table = pilot.app.query_one("#sub-table", DataTable)
            assert sub_table.row_count > 0, "Expected at least one subscription"
            sub_table.move_cursor(row=0, column=0)
            # Directly set selected_sub_id since move_cursor doesn't fire RowSelected
            nodes_tab = pilot.app.query_one("#nodes-tab")
            nodes_tab.selected_sub_id = sub_id
            await pilot.pause()

            # Click refresh
            await pilot.click("#btn-refresh-sub")
            await pilot.pause()
            await pilot.pause()  # wait for executor

            # Check that nodes appeared in nodes-table
            nodes_table = pilot.app.query_one("#nodes-table", DataTable)
            assert nodes_table.row_count > 0, (
                f"Expected nodes after refresh, got {nodes_table.row_count}"
            )


async def test_delete_subscription_with_confirm(
    temp_store_dir: Path, project_root: Path
):
    """Добавить подписку, выбрать её в таблице, нажать #btn-delete-sub,
    подтвердить в ConfirmModal, проверить что подписка удалена."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    # Pre-add a subscription to delete
    result = service.add_subscription("Delete Test", "https://example.com/delete")
    sub_id = result["subscription"]["id"]

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Switch to nodes tab
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Select the subscription
        sub_table = pilot.app.query_one("#sub-table", DataTable)
        assert sub_table.row_count > 0, "Expected at least one subscription"
        sub_table.move_cursor(row=0, column=0)
        nodes_tab = pilot.app.query_one("#nodes-tab")
        nodes_tab.selected_sub_id = sub_id
        await pilot.pause()

        # Click delete — opens ConfirmModal
        await pilot.click("#btn-delete-sub")
        await pilot.pause()

        # Confirm the deletion in ConfirmModal
        await pilot.click("#confirm-yes")
        await pilot.pause()
        await pilot.pause()  # wait for executor

        # Verify subscription is removed
        assert sub_table.row_count == 0, (
            f"Expected 0 subscriptions after deletion, got {sub_table.row_count}"
        )


async def test_import_subscription_cancel(
    temp_store_dir: Path, project_root: Path
):
    """Открыть модал, нажать Отмена, проверить что подписка не добавилась."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Switch to nodes tab
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Open import subscription modal
        await pilot.click("#btn-import-sub")
        await pilot.pause()

        # Fill the form (values should be ignored on cancel)
        modal = pilot.app.screen
        name_input = modal.query_one("#inp-sub-name", Input)
        name_input.value = "Cancelled Test"
        url_input = modal.query_one("#inp-sub-url", Input)
        url_input.value = "https://example.com/cancel"

        # Click cancel instead of add
        await pilot.click("#btn-sub-cancel")
        await pilot.pause()

        # Verify no subscription was added
        sub_table = pilot.app.query_one("#sub-table", DataTable)
        assert sub_table.row_count == 0, (
            f"Expected 0 subscriptions after cancel, got {sub_table.row_count}"
        )
