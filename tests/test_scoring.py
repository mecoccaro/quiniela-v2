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


# ─── Knockout stage ───────────────────────────────────────────────────────────

def test_knockout_exact_score_no_clasificado():
    # r16 exact (1-0 / 1-0), no winner info: resultado=12 + goals_a=3 + goals_b=3 + bonus=6 = 24
    assert score_prediction(1, 0, 1, 0, "r16", None, None, CONFIG) == 24


def test_knockout_correct_result_no_exact():
    # r16: predicted 2-0, official 3-1 — home win correct, goals_a wrong (2!=3), goals_b correct (0==1? no)
    # resultado=12 + goals_b correct? 0!=1, no. Just resultado=12 + goals_b? No.
    # predicted away=0, official away=1 → 0!=1 → goals_b wrong
    # predicted home=2, official home=3 → 2!=3 → goals_a wrong
    assert score_prediction(2, 0, 3, 1, "group", None, None, CONFIG) == 3


def test_r16_correct_result():
    # r16: predicted 2-0, official 3-1: resultado correct (home win)
    # goals_a: 2!=3 wrong; goals_b: 0!=1 wrong
    assert score_prediction(2, 0, 3, 1, "r16", None, None, CONFIG) == 12


def test_r16_correct_result_partial_goals():
    # r16: predicted 3-1, official 3-2: resultado correct (home win), goals_a correct (3==3), goals_b wrong
    assert score_prediction(3, 1, 3, 2, "r16", None, None, CONFIG) == 12 + 3


def test_knockout_draw_correct_clasificado():
    # r16: predicted 1-1, official 1-1, correct winner: resultado=12 + goals_a=3 + goals_b=3 + bonus=6 + clasificado=3 = 27
    assert score_prediction(1, 1, 1, 1, "r16", 10, 10, CONFIG) == 27


def test_knockout_draw_wrong_clasificado():
    # r16: predicted 1-1, official 1-1, wrong winner: resultado=12 + goals_a=3 + goals_b=3 + bonus=6 = 24
    assert score_prediction(1, 1, 1, 1, "r16", 10, 20, CONFIG) == 24


def test_knockout_clasificado_no_official_winner():
    # r16: exact score but official winner not set yet — no clasificado pts
    assert score_prediction(1, 1, 1, 1, "r16", 10, None, CONFIG) == 24


def test_knockout_wrong_result():
    # qf: home win predicted, away win actual
    assert score_prediction(2, 0, 0, 1, "qf", None, None, CONFIG) == 0


# ─── Clasificado inferred from decisive scoreline ────────────────────────────
# home_team_id=100, away_team_id=200. predicted_winner_id stays None for
# decisive predictions (the UX only stores it on draws).

def test_knockout_decisive_home_win_infers_clasificado():
    # r32: predicted 1-0 (home wins), official 1-0, official winner = home (100)
    # resultado=6 + goals_a=2 + goals_b=2 + bonus=4 + clasificado=2 = 16
    assert score_prediction(1, 0, 1, 0, "r32", None, 100, CONFIG, home_team_id=100, away_team_id=200) == 16


def test_knockout_decisive_home_win_non_exact_infers_clasificado():
    # r32: predicted 2-1 (home wins), official 1-0, official winner = home (100)
    # resultado=6 + clasificado=2 = 8 (no goals match)
    assert score_prediction(2, 1, 1, 0, "r32", None, 100, CONFIG, home_team_id=100, away_team_id=200) == 8


def test_knockout_decisive_away_win_infers_clasificado():
    # r32: predicted 0-2 (away wins), official 0-1, official winner = away (200)
    # resultado=6 + goals_a=2 (0==0) + clasificado=2 = 10
    assert score_prediction(0, 2, 0, 1, "r32", None, 200, CONFIG, home_team_id=100, away_team_id=200) == 10


def test_knockout_decisive_wrong_winner_no_clasificado():
    # r32: predicted 2-1 (home wins), official 0-1, official winner = away (200)
    # outcome wrong, goals_a wrong (2!=0), goals_b correct (1==1)=2, clasificado not awarded → 2
    assert score_prediction(2, 1, 0, 1, "r32", None, 200, CONFIG, home_team_id=100, away_team_id=200) == 2


def test_knockout_draw_pick_takes_precedence_over_inference():
    # r32: predicted draw 1-1 with explicit winner pick = home (100), official winner = home
    # resultado wrong (draw vs home win)=0 + goals_a=2 (1==1) + clasificado=2 = 4
    assert score_prediction(1, 1, 1, 0, "r32", 100, 100, CONFIG, home_team_id=100, away_team_id=200) == 4


def test_knockout_decisive_no_team_ids_no_clasificado():
    # Backward-compat: without team ids, decisive prediction can't infer winner
    assert score_prediction(1, 0, 1, 0, "r32", None, 100, CONFIG) == 14


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
    # final exact no winner: resultado=10 + goals_a=3 + goals_b=3 + bonus=5 = 21
    assert score_prediction(1, 0, 1, 0, "final", None, None, custom) == 21


# ─── DEFAULT_SCORING_CONFIG sanity checks ────────────────────────────────────

def test_default_config_champion_value():
    assert DEFAULT_SCORING_CONFIG["champion"] == 30


def test_default_config_top_scorer_value():
    assert DEFAULT_SCORING_CONFIG["top_scorer"] == 30
