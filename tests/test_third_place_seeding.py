"""
Unit tests for _build_third_pool_map backtracking implementation.

The function assigns ranked 3rd-place teams to pool-based bracket descriptors
(e.g. '3RD_ABCDF') using backtracking to avoid greedy assignment failures.
"""
import json
from pathlib import Path

import pytest

from apps.tournaments.services import _build_third_pool_map
from apps.tournaments.standings import TeamStanding

# Load the real bracket data so tests reflect production slot order and pool sets.
BRACKET_PATH = Path(__file__).resolve().parent.parent / "data" / "knockout_bracket.json"
R32_SLOTS: list[dict] = json.loads(BRACKET_PATH.read_text())["r32"]

# Descriptor order as they appear in the bracket (for reference in assertions):
# 3RD_ABCDF, 3RD_CDFGH, 3RD_CEFHI, 3RD_EHIJK, 3RD_BEFIJ, 3RD_AEHIJ, 3RD_EFGIJ, 3RD_DEIJL


def make_standing(team_id: int) -> TeamStanding:
    """Minimal TeamStanding with just a team_id."""
    return TeamStanding(team_id=team_id)


# ---------------------------------------------------------------------------
# Test 1: Happy path — one third from each of 8 distinct groups
# ---------------------------------------------------------------------------

def test_happy_path_all_slots_assigned() -> None:
    """8 thirds from 8 distinct groups that cover all slot pool sets — all 8 must be assigned.

    Groups chosen so that a valid complete assignment exists:
      3RD_ABCDF  ← A   (A ∈ {A,B,C,D,F})
      3RD_CDFGH  ← G   (G ∈ {C,D,F,G,H})
      3RD_CEFHI  ← C   (C ∈ {C,E,F,H,I})
      3RD_EHIJK  ← K   (K ∈ {E,H,I,J,K})
      3RD_BEFIJ  ← B   (B ∈ {B,E,F,I,J})
      3RD_AEHIJ  ← J   (J ∈ {A,E,H,I,J})
      3RD_EFGIJ  ← F   (F ∈ {E,F,G,I,J})
      3RD_DEIJL  ← L   (L ∈ {D,E,I,J,L})
    """
    group_map = {
        1: "A",  # best
        2: "G",
        3: "C",
        4: "K",
        5: "B",
        6: "J",
        7: "F",
        8: "L",  # worst
    }
    # Ranked best to worst: team_id 1..8
    ranked = [make_standing(tid) for tid in range(1, 9)]

    result = _build_third_pool_map(R32_SLOTS, ranked, group_map)

    # All 8 descriptors should be present and assigned (not None)
    assert "3RD_ABCDF" in result
    assert "3RD_CDFGH" in result
    assert "3RD_CEFHI" in result
    assert "3RD_EHIJK" in result
    assert "3RD_BEFIJ" in result
    assert "3RD_AEHIJ" in result
    assert "3RD_EFGIJ" in result
    assert "3RD_DEIJL" in result

    # No None values — every slot got a team
    for desc, team_id in result.items():
        assert team_id is not None, f"Slot {desc} was not assigned"

    # All assigned teams are distinct
    assigned_ids = [v for v in result.values() if v is not None]
    assert len(assigned_ids) == len(set(assigned_ids)), "Duplicate team assigned to multiple slots"

    # Each assigned team belongs to a valid group letter for its slot
    for desc, team_id in result.items():
        pool_letters = set(desc[4:])
        assert group_map[team_id] in pool_letters, (
            f"Team {team_id} (group {group_map[team_id]}) assigned to {desc} but its group is not in the pool"
        )


# ---------------------------------------------------------------------------
# Test 2: Greedy failure case — backtracking is required
# ---------------------------------------------------------------------------

def test_greedy_failure_backtracking_assigns_all_8() -> None:
    """
    Construct a scenario where a greedy algorithm would fail to fill all slots,
    but backtracking succeeds.

    8 thirds ranked best→worst: E(1), I(2), J(3), D(4), A(5), B(6), C(7), H(8).
    Groups available: {E, I, J, D, A, B, C, H} — no F, G, K, L.

    Greedy failure trace:
      3RD_ABCDF  → needs {A,B,C,D,F}: picks D(rank4) [D is eligible and beats A/B/C in rank]
      3RD_CDFGH  → needs {C,D,F,G,H}: D used, picks A... wait A∉{C,D,F,G,H}. Picks C(7) or H(8).
                   → greedy picks C(7).
      3RD_CEFHI  → needs {C,E,F,H,I}: picks E(1).
      3RD_EHIJK  → needs {E,H,I,J,K}: E used, picks I(2).
      3RD_BEFIJ  → needs {B,E,F,I,J}: E,I used, picks J(3).
      3RD_AEHIJ  → needs {A,E,H,I,J}: E,I,J used, picks A(5) or H(8). Picks A(5).
      3RD_EFGIJ  → needs {E,F,G,I,J}: E,I,J used; B,C,H remaining but none in {E,F,G,I,J}. → None!
      3RD_DEIJL  → needs {D,E,I,J,L}: D,E,I,J used; B,H remaining but none in {D,E,I,J,L}. → None!

    Backtracking finds a valid complete assignment, e.g.:
      3RD_ABCDF → A(5), 3RD_CDFGH → C(7), 3RD_CEFHI → H(8),
      3RD_EHIJK → E(1), 3RD_BEFIJ → B(6), 3RD_AEHIJ → J(3),
      3RD_EFGIJ → I(2), 3RD_DEIJL → D(4).
    """
    group_map = {
        1: "E",
        2: "I",
        3: "J",
        4: "D",
        5: "A",
        6: "B",
        7: "C",
        8: "H",
    }
    ranked = [make_standing(tid) for tid in range(1, 9)]

    result = _build_third_pool_map(R32_SLOTS, ranked, group_map)

    # All 8 slots must be present in the result
    expected_descriptors = {
        "3RD_ABCDF", "3RD_CDFGH", "3RD_CEFHI", "3RD_EHIJK",
        "3RD_BEFIJ", "3RD_AEHIJ", "3RD_EFGIJ", "3RD_DEIJL",
    }
    assert set(result.keys()) == expected_descriptors

    # All 8 slots must be assigned (not None) — backtracking finds a valid complete assignment
    for desc, team_id in result.items():
        assert team_id is not None, (
            f"Slot {desc} was not assigned — backtracking failed to find a solution"
        )

    # All assignments are distinct
    assigned_ids = [v for v in result.values() if v is not None]
    assert len(assigned_ids) == len(set(assigned_ids)), "Duplicate team assigned to multiple slots"

    # Each assigned team belongs to a valid group letter for its slot
    for desc, team_id in result.items():
        pool_letters = set(desc[4:])
        assert group_map[team_id] in pool_letters, (
            f"Team {team_id} (group {group_map[team_id]}) wrongly assigned to {desc}"
        )


# ---------------------------------------------------------------------------
# Test 3: Fewer than 8 thirds — remaining slots return None
# ---------------------------------------------------------------------------

def test_fewer_thirds_remaining_slots_none() -> None:
    """Only 4 thirds available; slots with no eligible team return None."""
    # 4 thirds from groups A, B, C, D
    group_map = {1: "A", 2: "B", 3: "C", 4: "D"}
    ranked = [make_standing(tid) for tid in range(1, 5)]

    result = _build_third_pool_map(R32_SLOTS, ranked, group_map)

    # All 8 descriptors must still appear as keys
    assert len(result) == 8

    # Slots with eligible teams should be assigned
    assigned = {desc: tid for desc, tid in result.items() if tid is not None}
    nones = {desc for desc, tid in result.items() if tid is None}

    # At most 4 assignments possible (we only have 4 teams)
    assert len(assigned) <= 4

    # Each assigned team is valid for its slot
    for desc, team_id in assigned.items():
        pool_letters = set(desc[4:])
        assert group_map.get(team_id) in pool_letters, (
            f"Team {team_id} wrongly assigned to {desc}"
        )

    # Slots that need groups outside {A,B,C,D} (like 3RD_EFGIJ which needs E/F/G/I/J)
    # must be None since no thirds from those groups exist
    assert result["3RD_EFGIJ"] is None, "3RD_EFGIJ should be None (no thirds from E,F,G,I,J)"


# ---------------------------------------------------------------------------
# Test 4: All thirds from the same group — only compatible slots get assigned
# ---------------------------------------------------------------------------

def test_all_same_group_only_compatible_slots_assigned() -> None:
    """
    8 thirds all from group E; only slots whose pool set contains E are assigned.
    Tests robustness: multiple teams from same group letter.
    """
    group_map = {i: "E" for i in range(1, 9)}
    ranked = [make_standing(tid) for tid in range(1, 9)]

    result = _build_third_pool_map(R32_SLOTS, ranked, group_map)

    # Count which descriptors contain 'E'
    e_slots = {d for d in result if "E" in d[4:]}
    non_e_slots = {d for d in result if "E" not in d[4:]}

    # E-containing slots should have a team assigned (up to 8 available)
    for desc in e_slots:
        assert result[desc] is not None, f"Slot {desc} (contains E) should be assigned"

    # Non-E slots cannot be assigned (no thirds from non-E groups)
    for desc in non_e_slots:
        assert result[desc] is None, f"Slot {desc} (no E) should be None"

    # Each assigned team must be from group E
    for desc, team_id in result.items():
        if team_id is not None:
            assert group_map[team_id] == "E"

    # No duplicates
    assigned_ids = [v for v in result.values() if v is not None]
    assert len(assigned_ids) == len(set(assigned_ids))
