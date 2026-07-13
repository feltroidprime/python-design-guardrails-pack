"""Certify the in-memory repository against the shared contract."""

import pytest

from __PACKAGE__.adapters.outbound.memory_repository import MemoryItemRepository
from tests.contract.item_repository_contract import ItemRepositoryContract


class TestMemoryItemRepository(ItemRepositoryContract):
    @pytest.fixture
    def repository(self) -> MemoryItemRepository:
        return MemoryItemRepository()
