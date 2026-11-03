from decimal import Decimal

import pytest

from app.spend.caps import RunSpendCapExceeded, SystemBudget


def test_unknown_scope_is_refused():
    with pytest.raises(ValueError):
        RunSpendCapExceeded("x", scope="nope")


def test_system_budget_adds_and_resets():
    b = SystemBudget()
    b.add(5)
    b.add("2.5")
    b.reset()
    assert b._entries == []
