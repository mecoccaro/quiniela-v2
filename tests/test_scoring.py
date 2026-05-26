from apps.leaderboard.scoring import DEFAULT_SCORING_CONFIG, score_prediction

CONFIG = DEFAULT_SCORING_CONFIG


# ─── Group stage ──────────────────────────────────────────────────────────────

def test_group_exact_score():
    assert score_prediction(2, 1, 2, 1, "group", None, None, CONFIG) == CONFIG["group"]["exact_score"]


def test_group_correct_result_home_win():
    assert score_prediction(3, 0, 2, 1, "group", None, None, CONFIG) == CONFIG["group"]["correct_result"]


def test_group_correct_result_draw():
    assert score_prediction(1, 1, 0, 0, "group", None, None, CONFIG) == CONFIG["group"]["correct_result"]


def test_group_correct_result_away_win():
    assert score_prediction(0, 2, 0, 1, "group", None, None, CONFIG) == CONFIG["group"]["correct_result"]


def test_group_wrong_result():
    assert score_prediction(2, 0, 0, 1, "group", None, None, CONFIG) == 0


def test_group_wrong_both():
    assert score_prediction(1, 0, 0, 2, "group", None, None, CONFIG) == 0


# ─── Knockout stage ───────────────────────────────────────────────────────────

def test_knockout_exact_score():
    assert score_prediction(1, 0, 1, 0, "r16", None, None, CONFIG) == CONFIG["r16"]["exact_score"]


def test_knockout_correct_result():
    assert score_prediction(2, 0, 3, 1, "r16", None, None, CONFIG) == CONFIG["r16"]["correct_result"]


def test_knockout_pens_winner_correct():
    # Draw predicted with correct pens winner
    pts = score_prediction(1, 1, 1, 1, "r16", team_a := 10, team_a, CONFIG)
    assert pts == CONFIG["r16"]["exact_score"] + CONFIG["r16"]["pens_winner"]


def test_knockout_pens_winner_wrong():
    pts = score_prediction(1, 1, 1, 1, "r16", 10, 20, CONFIG)
    assert pts == CONFIG["r16"]["exact_score"]  # exact score but wrong pens winner


def test_knockout_correct_result_with_pens_winner():
    # Non-exact draw but correct winner
    pts = score_prediction(0, 0, 1, 1, "r16", team_a := 10, team_a, CONFIG)
    assert pts == CONFIG["r16"]["correct_result"] + CONFIG["r16"]["pens_winner"]


def test_knockout_pens_winner_no_official_winner():
    # No official knockout winner set yet — no pens bonus
    pts = score_prediction(1, 1, 1, 1, "r16", 10, None, CONFIG)
    assert pts == CONFIG["r16"]["exact_score"]


def test_knockout_pens_winner_not_applicable_for_group():
    # pens winner bonus never applies to group stage
    pts = score_prediction(1, 1, 1, 1, "group", 10, 10, CONFIG)
    assert pts == CONFIG["group"]["exact_score"]


def test_knockout_wrong_result():
    assert score_prediction(2, 0, 0, 1, "qf", None, None, CONFIG) == 0


# ─── Custom config — flat (legacy) format still supported ────────────────────

def test_custom_config_flat_format():
    custom = {"exact_score": 5, "correct_result": 2, "pens_winner": 2, "champion": 10, "top_scorer": 5}
    assert score_prediction(2, 1, 2, 1, "group", None, None, custom) == 5
    assert score_prediction(3, 0, 2, 1, "group", None, None, custom) == 2


# ─── Per-stage config overrides ───────────────────────────────────────────────

def test_per_stage_config_different_values():
    custom = {
        "group": {"exact_score": 2, "correct_result": 1},
        "final": {"exact_score": 10, "correct_result": 5, "pens_winner": 3},
    }
    assert score_prediction(2, 1, 2, 1, "group", None, None, custom) == 2
    assert score_prediction(1, 0, 1, 0, "final", None, None, custom) == 10
