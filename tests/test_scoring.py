from apps.leaderboard.scoring import DEFAULT_SCORING_CONFIG, score_prediction

CONFIG = DEFAULT_SCORING_CONFIG


# ─── Group stage ──────────────────────────────────────────────────────────────

def test_group_exact_score():
    # resultado=3 + goals_a=1 + goals_b=1 + bonus=2 = 7
    assert score_prediction(2, 1, 2, 1, "group", None, None, CONFIG) == 7


def test_group_correct_result_home_win():
    # resultado=3 + goals_b=1 (away score matches: 0==1? No. 0!=1) → resultado=3 + goals_b correct (0==1 no)
    # predicted 3-0, official 2-1: resultado correct (home win), goals_a wrong (3!=2), goals_b wrong (0!=1)
    assert score_prediction(3, 0, 2, 1, "group", None, None, CONFIG) == 3


def test_group_correct_result_home_win_partial_goals():
    # predicted 3-1, official 2-1: resultado correct (home win), goals_a wrong, goals_b correct
    assert score_prediction(3, 1, 2, 1, "group", None, None, CONFIG) == 3 + 1


def test_group_correct_result_draw():
    # predicted 1-1, official 0-0: resultado correct (draw), goals_a wrong, goals_b wrong
    assert score_prediction(1, 1, 0, 0, "group", None, None, CONFIG) == 3


def test_group_correct_result_away_win():
    # predicted 0-2, official 0-1: resultado correct (away win), goals_a correct (0==0), goals_b wrong
    assert score_prediction(0, 2, 0, 1, "group", None, None, CONFIG) == 3 + 1


def test_group_wrong_result():
    # predicted 2-0 (home win), official 0-1 (away win): wrong resultado, goals wrong
    assert score_prediction(2, 0, 0, 1, "group", None, None, CONFIG) == 0


def test_group_wrong_both():
    # predicted 1-0 (home win), official 0-2 (away win): wrong
    assert score_prediction(1, 0, 0, 2, "group", None, None, CONFIG) == 0


def test_group_ignores_clasificado():
    # Even when predicted_winner_id == official_knockout_winner_id, group stage gives no clasificado pts
    assert score_prediction(2, 1, 2, 1, "group", 10, 10, CONFIG) == 7


# ─── Knockout stage: team-aware tier scoring ─────────────────────────────────
# Real match: home team=100, away team=200. r32 values:
#   resultado=6, goals_a=2, goals_b=2, bonus=4, clasificado=2.
# Helper kwargs: ph_team/pa_team = predicted bracket teams for the slot.


def ko(ph, pa, oh, oa, stage, pred_winner, off_winner, ph_team, pa_team, rh=100, ra=200):
    return score_prediction(
        ph, pa, oh, oa, stage, pred_winner, off_winner, CONFIG,
        home_team_id=rh, away_team_id=ra,
        predicted_home_team_id=ph_team, predicted_away_team_id=pa_team,
    )


# Tier 1 — both predicted teams correct on their side
def test_t1_exact_score():
    # r32 1-0, both teams right, exact: resultado6 + goals_a2 + goals_b2 + bonus4 + clasificado2 = 16
    assert ko(1, 0, 1, 0, "r32", None, 100, 100, 200) == 16


def test_t1_correct_winner_not_exact():
    # r32 predicted 2-1 (home wins), official 1-0: resultado6 + clasificado2 = 8
    assert ko(2, 1, 1, 0, "r32", None, 100, 100, 200) == 8


def test_t1_partial_goals():
    # r32 predicted 1-2 (away wins), official 0-2 (away wins): away team(200) wins both →
    # resultado6 + goals_b2 (2==2) + clasificado2 = 10
    assert ko(1, 2, 0, 2, "r32", None, 200, 100, 200) == 10


def test_t1_wrong_winner():
    # r32 predicted 2-1 (home wins), official 0-1 (away wins): resultado wrong, goals_b2 (1==1), no clasificado = 2
    assert ko(2, 1, 0, 1, "r32", None, 200, 100, 200) == 2


def test_t1_draw_to_pens_correct_winner():
    # r32 predicted 1-1 pens, winner pick=home(100); official 1-1 pens, winner=home(100):
    # resultado6 (both pens) + goals_a2 + goals_b2 + bonus4 + clasificado2 = 16
    assert ko(1, 1, 1, 1, "r32", 100, 100, 100, 200) == 16


def test_t1_draw_to_pens_wrong_winner():
    # same but official winner = away(200): resultado6 + goals4 + bonus4 = 14 (no clasificado)
    assert ko(1, 1, 1, 1, "r32", 100, 200, 100, 200) == 14


def test_t1_official_winner_not_set_yet():
    # exact 1-0 but knockout_winner still NULL → no clasificado: 6+2+2+4 = 14
    assert ko(1, 0, 1, 0, "r32", None, None, 100, 200) == 14


# Tier 2 — exactly one predicted team correct on its side (no bonus, goals on both sides)
def test_t2_home_team_correct_exact_scoreline():
    # predicted away team wrong (999). 1-0 exact, home wins: resultado6 + goals_a2 + goals_b2 + clasificado2 = 12 (no bonus)
    assert ko(1, 0, 1, 0, "r32", None, 100, 100, 999) == 12


def test_t2_away_team_correct():
    # predicted home team wrong (999), away team correct (200). predicted 0-1 (away 200 wins), official 0-1:
    # resultado6 + goals_a2 + goals_b2 + clasificado2 = 12
    assert ko(0, 1, 0, 1, "r32", None, 200, 999, 200) == 12


def test_t2_wrong_predicted_winner_zeroes_resultado_and_ganador():
    # home team correct(100) but predicted away(999) to win 0-2; official home wins 1-0:
    # resultado: predicted winner 999 != real 100 → 0; goals none; clasificado 0 → 0
    assert ko(0, 2, 1, 0, "r32", None, 100, 100, 999) == 0


# Tier 3 — a predicted team is in the match but on the wrong side
def test_t3_right_team_wrong_side_wins():
    # real away team(200) was predicted as home and to win 2-0; official 0-1 (away 200 wins):
    # decisive both, predicted winner=200 == real winner 200 → resultado6 + clasificado2 = 8 (no goals/bonus in T3)
    assert ko(2, 0, 0, 1, "r32", None, 200, 200, 999) == 8


def test_t3_right_team_wrong_side_but_loses():
    # real home team(100) predicted as away; predicted 0-2 (away=100 wins); official 1-0 (home 100 wins):
    # predicted winner=100 == real winner 100 → resultado6 + clasificado2 = 8
    assert ko(0, 2, 1, 0, "r32", None, 100, 999, 100) == 8


def test_t3_no_goals_or_bonus_even_when_scoreline_matches():
    # real away(200) predicted as home, exact-looking 1-0 but teams swapped; official 0-1:
    # predicted home=200 wins by score; real winner=200 → resultado6 + clasificado2 = 8; no goals despite 1/0 numbers
    assert ko(1, 0, 0, 1, "r32", None, 200, 200, 999) == 8


# Tier 0 — no predicted team is in the real match (the Boncan case)
def test_t0_predicted_teams_not_in_match():
    # predicted Korea(777) vs Japan(888) 1-0; real match is 100 vs 200 → 0 points regardless of scoreline
    assert ko(1, 0, 1, 0, "r32", None, 100, 777, 888) == 0


def test_t0_even_with_winner_pick():
    assert ko(1, 1, 1, 1, "r32", 777, 100, 777, 888) == 0


def test_knockout_no_predicted_teams_is_tier0():
    # No bracket info at all (both None) → can't place teams → 0
    assert score_prediction(1, 0, 1, 0, "r32", None, 100, CONFIG, home_team_id=100, away_team_id=200) == 0


# ─── Legacy flat-format config still supported ───────────────────────────────

def test_legacy_flat_config_exact():
    # Flat format: maps to v4 via legacy fallback (correct_goals = 0)
    custom = {"exact_score": 5, "correct_result": 2, "pens_winner": 2, "champion": 10, "top_scorer": 5}
    # exact hit: correct_resultado=2 + bonus_exact_score=5 = 7 (goals are 0 in legacy)
    assert score_prediction(2, 1, 2, 1, "group", None, None, custom) == 7


def test_legacy_flat_config_result_only():
    # Flat format, correct result but not exact: only correct_resultado points
    custom = {"exact_score": 5, "correct_result": 2, "pens_winner": 2, "champion": 10, "top_scorer": 5}
    assert score_prediction(3, 0, 2, 1, "group", None, None, custom) == 2


# ─── Per-stage v4 config overrides ───────────────────────────────────────────

def test_per_stage_v4_config():
    custom = {
        "group": {"correct_resultado": 2, "correct_goals_team_a": 0, "correct_goals_team_b": 0, "bonus_exact_score": 1},
        "final": {"correct_resultado": 10, "correct_clasificado": 5, "correct_goals_team_a": 3, "correct_goals_team_b": 3, "bonus_exact_score": 5},
    }
    # group exact: resultado=2 + bonus=1 = 3
    assert score_prediction(2, 1, 2, 1, "group", None, None, custom) == 3
    # final exact, both teams correct (T1), winner not set: resultado=10 + goals_a=3 + goals_b=3 + bonus=5 = 21
    assert score_prediction(
        1, 0, 1, 0, "final", None, None, custom,
        home_team_id=100, away_team_id=200,
        predicted_home_team_id=100, predicted_away_team_id=200,
    ) == 21


# ─── DEFAULT_SCORING_CONFIG sanity checks ────────────────────────────────────

def test_default_config_champion_value():
    assert DEFAULT_SCORING_CONFIG["champion"] == 30


def test_default_config_top_scorer_value():
    assert DEFAULT_SCORING_CONFIG["top_scorer"] == 30
