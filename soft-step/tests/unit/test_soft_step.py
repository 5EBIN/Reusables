"""a "non-fatal" step logs expected failures as a warning, and a programming error at ERROR with its traceback, counted, re-raised outside production (app/core/soft_step.py)."""
import asyncio
import logging
import re
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from app.core import soft_step as S


@pytest.fixture(autouse=True)
def _local(monkeypatch):
    monkeypatch.setattr(S, "_is_production", lambda: False)
    S._counts.clear()


@pytest.mark.parametrize("exc", [asyncio.TimeoutError(), TimeoutError("t"), ConnectionError("down"), OSError("disk"), OperationalError("select 1", {}, Exception("db gone"))])
def test_expected_errors_log_a_warning_and_never_raise(exc, caplog):
    with caplog.at_level(logging.WARNING):
        S.soft_failure("a step", exc)
    assert [r.levelname for r in caplog.records] == ["WARNING"] and S.counts() == {}


@pytest.mark.parametrize("exc", [NameError("x"), UnboundLocalError("x"), TypeError("x"), AttributeError("x"), KeyError("x"), ImportError("x")])
def test_a_programming_error_is_logged_at_error_counted_and_raised_outside_production(exc, caplog):
    with caplog.at_level(logging.WARNING), pytest.raises(type(exc)):
        S.soft_failure("a step", exc)
    assert caplog.records[-1].levelname == "ERROR" and caplog.records[-1].exc_info and S.counts() == {"a step": 1}


def test_in_production_a_programming_error_is_logged_and_the_run_goes_on(monkeypatch, caplog):
    monkeypatch.setattr(S, "_is_production", lambda: True)
    with caplog.at_level(logging.WARNING):
        S.soft_failure("a step", TypeError("x"))
    assert caplog.records[-1].levelname == "ERROR" and S.counts() == {"a step": 1}


def test_any_other_error_is_a_warning_as_before(caplog):
    with caplog.at_level(logging.WARNING):
        S.soft_failure("a step", ValueError("bad value"))
    assert [r.levelname for r in caplog.records] == ["WARNING"]


def test_detail_and_the_class_only_form(caplog):
    with caplog.at_level(logging.WARNING):
        S.soft_failure("a step", ValueError("secret text"), "src/a.ts", message=False)
    text = caplog.records[-1].getMessage()
    assert "src/a.ts" in text and "ValueError" in text and "secret text" not in text


def test_the_with_form_does_the_same():
    with S.soft_step("a block"):
        raise OSError("disk")                                                    # swallowed
    with pytest.raises(AttributeError), S.soft_step("a block"):
        raise AttributeError("nope")
