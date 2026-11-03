import copy
import json
import logging
import pickle

import pytest

from app.core.secret import Secret, scrub

KEY = "<api-key>"


def test_every_way_of_printing_shows_only_the_mask():
    s = Secret(KEY)
    for text in (repr(s), str(s), f"{s}", f"{s!r}", "%s" % s, "{}".format(s), format(s, ">30")):  # noqa: UP031, UP032 (every formatting style is the point)
        assert KEY not in text and "0123456789abcdef" not in text
    assert str(s) == "sk-or-…" + KEY[-4:]


def test_reveal_is_the_only_way_to_the_value():
    assert Secret(KEY).reveal() == KEY
    assert not Secret("") and not Secret(None) and Secret(KEY)


def test_short_values_show_nothing():
    assert str(Secret("short")) == "…" and str(Secret("")) == ""


def test_cannot_be_serialised_pickled_or_changed():
    s = Secret(KEY)
    with pytest.raises(TypeError):
        json.dumps({"k": s})
    with pytest.raises(TypeError):
        pickle.dumps(s)
    with pytest.raises(AttributeError):
        s._v = "x"
    assert copy.deepcopy(s) is s


def test_logging_a_secret_never_writes_the_value(caplog):
    s = Secret(KEY)
    with caplog.at_level(logging.INFO):
        logging.getLogger("t").info("key %s and %r", s, s)
        logging.getLogger("t").error("failed with %s", s, exc_info=ValueError(f"bad {s}"))
    assert KEY not in caplog.text and "0123456789abcdef" not in caplog.text


def test_scrub_removes_real_values_from_free_text():
    s = Secret(KEY)
    msg = f"401 for Authorization: Bearer {KEY} on /chat"
    out = scrub(msg, s)
    assert KEY not in out and "sk-or-…" + KEY[-4:] in out
    assert scrub("nothing here", s) == "nothing here"
    assert scrub(msg, None, "short") == msg                 # values under 8 characters are never used as a search pattern
