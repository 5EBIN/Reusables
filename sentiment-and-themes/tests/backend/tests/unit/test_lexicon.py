import json
import re

import pytest

from app.core import lexicon as lx
from app.core.sentiment import SETS, golden_rows, golden_report, from_lexicon
from app.core.text_analysis import sentiment

DATA = json.loads(lx.PATH.read_text(encoding="utf-8"))


def label(text):
    return sentiment(text)[0]


def test_every_word_is_listed_once_and_never_as_both_positive_and_negative():
    seen = {}
    for lang in ("en", "ar"):
        for key in ("pos_strong", "pos", "neg_strong", "neg"):
            for w in DATA[lang][key]:
                n = lx._n(w)
                assert n not in seen, f"{w!r} is in {key} and {seen[n]}"
                seen[n] = key
                assert len(n) >= 3 and n == n.strip(), w                       # too-short entries match inside other words


def test_a_negator_is_never_also_a_sentiment_word():
    words = {lx._n(w) for lang in ("en", "ar") for key in ("pos_strong", "pos", "neg_strong", "neg") for w in DATA[lang][key]}
    assert not words & {lx._n(w) for lang in ("en", "ar") for w in DATA[lang]["negators"]}


def test_phrases_are_not_repeated_between_lists():
    for lang in ("en", "ar"):
        pos = {lx._n(p) for p, _ in DATA[lang]["phrases"]["pos"]}
        neg = {lx._n(p) for p, _ in DATA[lang]["phrases"]["neg"]}
        assert not pos & neg and all(w in (1, 2) for _, w in DATA[lang]["phrases"]["pos"] + DATA[lang]["phrases"]["neg"])


@pytest.mark.parametrize("text", ["I ate a chocolate bar", "the glove box", "a badge and a lace", "the latest news", "kind of ok", "my belated gift", "the issued receipt"])
def test_words_only_match_whole_words(text):
    assert label(text) == 0


@pytest.mark.parametrize("text,expected", [
    # hospitality, healthcare, government, education, transport, employer, property
    ("The room was spotless and the staff were welcoming", 1),
    ("Check-in was a nightmare and the food was bland", -1),
    ("The nurses were caring and attentive", 1),
    ("Long wait, nobody answered the phone", -1),
    ("So much red tape for a simple form", -1),
    ("The lecturers are inspiring and the course is well organised", 1),
    ("Trains are overcrowded and always delayed", -1),
    ("My manager is supportive and the hours are flexible", 1),
    ("Burnout is real here, everyone is overworked and underpaid", -1),
    ("There is a leak in the ceiling and cockroaches in the kitchen", -1),
    ("Cleanest and quietest building I have lived in, the gym is fantastic", 1),
])
def test_survey_sentences_across_sectors(text, expected):
    assert label(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("والخدمة ممتازة", 1), ("بالتاخير الدائم", -1), ("الموظفين متعاونين ومحترمين", 1), ("المكان وسخ والمكيف خربان", -1),
    ("مره حلو والله", 1), ("الخدمة مو زينة", -1), ("ما في مشاكل ابدا", 1), ("لا انصح فيه", -1), ("تعامل راقي جدا", 1),
    ("الصيانة بطيئة والرد ما يجي", -1), ("تسلم ايديكم على الجهد", 1),
])
def test_arabic_prefixes_endings_and_gulf_wording(text, expected):
    assert label(text) == expected


def test_boosters_raise_and_dampeners_lower_the_weight():
    base = lx.evidence("the room was clean")[0]
    assert lx.evidence("the room was very clean")[0] == base * lx.BOOST
    assert lx.evidence("the room was slightly clean")[0] == base * lx.DAMPEN
    assert lx.evidence("الخدمة سريعه جدا")[0] > lx.evidence("الخدمة سريعه")[0]


def test_strong_words_outweigh_mild_ones():
    assert lx.evidence("excellent")[0] == 2 and lx.evidence("good")[0] == 1 and lx.evidence("terrible")[1] == 2


def test_mixed_comments_are_never_confident():
    for text in ["The gym is great but the parking is terrible", "Friendly staff but slow service", "الخدمة حلوة بس المواقف قليلة"]:
        lab, conf = sentiment(text)
        assert conf < 0.6 or lab == 0
    assert sentiment("excellent, outstanding, amazing, but one slow lift")[1] <= 0.7       # clear lean, yet mixed: capped


def test_double_negation_and_window():
    assert label("not bad at all") == 1
    assert label("not that I would ever say so out loud but it was great") == 1            # the negator is too far from "great"


def test_both_golden_sets_load_and_are_balanced():
    for which in SETS:
        rows = golden_rows(which)
        assert len(rows) >= 30 and {r["lang"] for r in rows} == {"en", "ar"} and {r["label"] for r in rows} == {"positive", "neutral", "negative"}
        report = golden_report(from_lexicon, which=which)
        assert report["n"] == len(rows)


@pytest.mark.golden
def test_the_curated_list_beats_a_floor_on_both_sets():
    """A guard against regressions, not a quality claim: these are small sets written by the developers."""
    assert golden_report(from_lexicon, which="core")["accuracy"] >= 0.8
    assert golden_report(from_lexicon, which="survey")["accuracy"] >= 0.65


def test_lexicon_file_is_valid_json_with_a_version():
    assert re.fullmatch(r"[a-z]+-\d+", DATA["version"]) and lx.load().version == DATA["version"]
