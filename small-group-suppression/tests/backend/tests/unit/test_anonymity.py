import pytest
from hypothesis import given, settings, strategies as st

from app.core.anonymity import OTHER, aggregate, can_be_anonymous, release_comments, scrub, slice_allowed, suppress_matrix

S = st.floats(1, 5, allow_nan=False)
G = st.lists(S, min_size=0, max_size=12)


def test_groups_below_min_hidden_and_not_in_combined():
    a = aggregate({"self": [4.0], "manager": [3.8], "peer": [3, 4, 3, 4, 4], "direct_report": [5, 1, 2]}, 5)
    assert a.groups["peer"].shown and not a.groups["direct_report"].shown and a.groups["direct_report"].mean is None
    assert a.hidden == ["direct_report"]
    assert a.combined.n == 5 + 1                                       # peers + visible manager only
    assert round(a.combined.mean, 2) == round((3 + 4 + 3 + 4 + 4 + 3.8) / 6, 2)


def test_small_groups_merge_only_if_merged_meets_min():
    a = aggregate({"peer": [3, 4, 5], "external": [2, 4]}, 5)
    assert a.groups[OTHER].n == 5 and a.groups[OTHER].merged_from == ["external", "peer"] and not a.hidden
    b = aggregate({"peer": [3, 4], "external": [2, 4]}, 5)
    assert OTHER not in b.groups and sorted(b.hidden) == ["external", "peer"] and b.combined is None


def test_single_small_group_never_merged_with_itself():
    a = aggregate({"peer": [3, 4, 5, 3]}, 5)
    assert a.hidden == ["peer"] and a.groups["peer"].mean is None


def test_self_always_separate_and_shown():
    a = aggregate({"self": [4.1]}, 5)
    assert a.groups["self"].shown and a.combined is None


def test_manager_hidden_mode_excluded_everywhere():
    a = aggregate({"manager": [1.0], "peer": [5] * 5}, 5, manager_visible=False)
    assert "manager" not in a.groups and a.combined.mean == 5.0


@settings(max_examples=300, deadline=None)
@given(self_=G, mgr=G, peer=G, dr=G, mm=G, ext=G, n=st.integers(2, 7))
def test_property_hidden_scores_never_influence_released_numbers(self_, mgr, peer, dr, mm, ext, n):
    data = {"self": self_, "manager": mgr, "peer": peer, "direct_report": dr, "matrix_manager": mm, "external": ext}
    a = aggregate(data, n)
    for k, g in a.groups.items():
        if g.shown and k not in ("self", "manager"):
            assert g.n >= n                                              # no released group below min
        if not g.shown:
            assert g.mean is None
    # perturb every hidden raters' scores: nothing released may change
    hidden = set(a.hidden)
    pert = {k: ([9.0] * len(v) if k in hidden else v) for k, v in data.items()}
    b = aggregate(pert, n)
    assert {k: g.mean for k, g in a.groups.items()} == {k: g.mean for k, g in b.groups.items()}
    assert (a.combined.mean if a.combined else None) == (b.combined.mean if b.combined else None)


@settings(max_examples=200, deadline=None)
@given(peer=st.lists(S, min_size=0, max_size=9), dr=st.lists(S, min_size=0, max_size=9), n=st.integers(3, 6))
def test_property_subtraction_attack_cannot_isolate_rater(peer, dr, n):
    """Remove one rater at a time: if the released outputs change, that rater must belong to a released group of size >= n."""
    base = aggregate({"peer": peer, "direct_report": dr}, n)
    for key, vals in (("peer", peer), ("direct_report", dr)):
        if not vals:
            continue
        less = {"peer": peer, "direct_report": dr}
        less[key] = vals[:-1]
        alt = aggregate(less, n)
        shown = lambda a_: ({k: g.mean for k, g in a_.groups.items() if g.shown}, a_.combined.mean if a_.combined else None)  # noqa: E731
        changed = shown(base) != shown(alt)
        if changed:
            assert len(vals) >= n or (OTHER in base.groups)             # only visible through a group that met the minimum


@pytest.mark.parametrize("p,n,ok", [(6, 5, True), (5, 5, False), (4, 3, True), (3, 3, False)])
def test_can_be_anonymous(p, n, ok):
    assert can_be_anonymous(p, n) is ok


def test_comments_gated_shuffled_scrubbed():
    c = {"peer": [f"{i} Rania said hello" for i in range(5)], "direct_report": ["a", "b"], "self": ["mine"], "manager": ["boss"]}
    out = release_comments(c, 5, "cycle1", ["Rania <company>"])
    assert set(out) == {"peer"} and all("[name]" in x and "Rania" not in x for x in out["peer"])
    assert out == release_comments(c, 5, "cycle1", ["Rania <company>"])           # deterministic
    assert sorted(out["peer"]) == sorted(release_comments(c, 5, "cycle2", ["Rania <company>"])["peer"])   # same content, seed-dependent order


@pytest.mark.parametrize("text,names,out", [("Ask Omar", ["Omar Siddiqui"], "Ask [name]"), ("قال عمر", ["عمر الصديقي"], "قال [name]"), ("ab", ["ab"], "ab"),
                                            ("OMAR!", ["omar x"], "[name]!"), ("nothing", ["Omar"], "nothing")])
def test_scrub(text, names, out):
    assert scrub(text, names) == out


def test_slice_allowed():
    sizes = {"HR": 4, "Ops": 9}
    assert not slice_allowed(sizes, ["HR"], 5) and slice_allowed(sizes, ["HR", "Ops"], 5)


def test_matrix_complementary_suppression():
    counts = {("HR", "a"): 4, ("HR", "b"): 20, ("Ops", "a"): 30, ("Ops", "b"): 40, ("IT", "a"): 12, ("IT", "b"): 15}
    h = suppress_matrix(counts, 5)
    assert h[("HR", "a")] and h[("HR", "b")]                         # row partner hidden too
    assert h[("IT", "a")] and h[("IT", "b")] and not h[("Ops", "a")] and not h[("Ops", "b")]   # smallest column partners hidden, largest kept


@settings(max_examples=100, deadline=None)
@given(st.dictionaries(st.tuples(st.sampled_from("ABCD"), st.sampled_from("xyz")), st.integers(0, 30), min_size=1, max_size=12), st.integers(3, 6))
def test_matrix_no_line_with_exactly_one_hidden_cell(counts, n):
    h = suppress_matrix(counts, n)
    lines = {}
    for (r, c) in counts:
        lines.setdefault(("r", r), []).append((r, c))
        lines.setdefault(("c", c), []).append((r, c))
    for line in lines.values():
        if len(line) > 1:
            assert sum(h[k] for k in line) != 1
