"""Structural anonymity for multi-rater feedback and group slicing. Pure and property-tested.

Rules: a group's statistic is released only if n >= min_n. Groups below min_n are merged into 'other raters' only if the merged
group meets min_n, otherwise hidden. 'Combined' is computed ONLY from released groups, so hidden raters never influence any
released number (no subtraction attack is possible). Self is always separate. The manager group is identified by role and shown
separately when allowed."""
import hashlib
import random
import re
from dataclasses import dataclass, field
from statistics import mean

SELF, MANAGER = "self", "manager"
PEER_TYPES = ("peer", "direct_report", "matrix_manager", "external")
OTHER = "other_raters"


@dataclass
class GroupStat:
    key: str
    n: int
    mean: float | None
    shown: bool
    merged_from: list[str] = field(default_factory=list)


@dataclass
class Aggregate:
    groups: dict[str, GroupStat]
    combined: GroupStat | None
    hidden: list[str]


def aggregate(scores: dict[str, list[float]], min_n: int, manager_visible: bool = True) -> Aggregate:
    """scores: rater_type -> list of scores for ONE competency (or overall)."""
    if min_n < 2:
        raise ValueError("min_n must be >= 2")
    groups: dict[str, GroupStat] = {}
    hidden: list[str] = []
    if scores.get(SELF):
        groups[SELF] = GroupStat(SELF, len(scores[SELF]), round(mean(scores[SELF]), 2), True)
    if scores.get(MANAGER):
        v = scores[MANAGER]
        if manager_visible:
            groups[MANAGER] = GroupStat(MANAGER, len(v), round(mean(v), 2), True)
    shown_pool: list[float] = []
    small: dict[str, list[float]] = {}
    for t in PEER_TYPES:
        v = scores.get(t, [])
        if not v:
            continue
        if len(v) >= min_n:
            groups[t] = GroupStat(t, len(v), round(mean(v), 2), True)
            shown_pool += v
        else:
            small[t] = v
    if small:
        merged = [x for v in small.values() for x in v]
        if len(merged) >= min_n and len(small) > 1:
            groups[OTHER] = GroupStat(OTHER, len(merged), round(mean(merged), 2), True, sorted(small))
            shown_pool += merged
        else:
            hidden += sorted(small)
            for t, v in small.items():
                groups[t] = GroupStat(t, len(v), None, False)
    if MANAGER in groups:
        shown_pool = shown_pool + scores[MANAGER]
    elif scores.get(MANAGER) and not manager_visible and len(scores[MANAGER]) >= 1:
        pass                                   # manager hidden: excluded from every released number
    combined = GroupStat("combined", len(shown_pool), round(mean(shown_pool), 2), True) if len(shown_pool) >= 1 and (
        len(shown_pool) >= min_n or (MANAGER in groups and len(shown_pool) == len(scores[MANAGER]))) else None
    return Aggregate(groups, combined, hidden)


def can_be_anonymous(participants: int, min_n: int) -> bool:
    return participants >= min_n + 1


def release_comments(comments_by_group: dict[str, list[str]], min_n: int, seed: str, roster_names: list[str]) -> dict[str, list[str]]:
    """Comments only for groups with n >= min_n (n = group size, including those without comments), shuffled deterministically, names scrubbed."""
    out: dict[str, list[str]] = {}
    for g, items in comments_by_group.items():
        if g in (SELF, MANAGER) or len(items) < min_n:
            continue
        rng = random.Random(hashlib.sha256(f"{seed}|{g}".encode()).hexdigest())
        shuffled = items[:]
        rng.shuffle(shuffled)
        out[g] = [scrub(c, roster_names) for c in shuffled]
    return out


def scrub(text: str, names: list[str]) -> str:
    """Token-level scrub of roster names (>=3 chars, any script) from free text."""
    for n in sorted({x for part in names for x in re.split(r"\s+", part.strip()) if len(x) >= 3}, key=len, reverse=True):
        text = re.sub(re.escape(n), "[name]", text, flags=re.IGNORECASE)
    return text


def slice_allowed(group_sizes: dict[str, int], chosen: list[str], min_n: int) -> bool:
    """Drill-down guard (engagement/dashboard filters): the combined slice must meet min_n."""
    return sum(group_sizes.get(k, 0) for k in chosen) >= min_n


def suppress_matrix(counts: dict[tuple, int], min_n: int, row_totals: bool = True) -> dict[tuple, bool]:
    """Matrix suppression (department x dimension). A cell is hidden if n < min_n. Complementary suppression: if exactly one cell in a row
    (or column) is hidden while row/column totals are shown, also hide the smallest other cell in that line so the hidden value cannot be derived."""
    hidden = {k: v < min_n for k, v in counts.items()}
    rows: dict = {}
    cols: dict = {}
    for r, c in counts:
        rows.setdefault(r, []).append((r, c))
        cols.setdefault(c, []).append((r, c))
    changed = True
    while changed:
        changed = False
        for line in list(rows.values()) + list(cols.values()):
            hid = [k for k in line if hidden[k]]
            if len(hid) == 1 and len(line) > 1:
                cand = sorted((k for k in line if not hidden[k]), key=lambda k: counts[k])
                if cand:
                    hidden[cand[0]] = True
                    changed = True
    return hidden
