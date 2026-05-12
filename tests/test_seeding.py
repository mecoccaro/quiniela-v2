import pytest
from django.core.management import call_command

from apps.tournaments.models import Match, Team, TournamentTeam


@pytest.mark.django_db
def test_load_wc2026_creates_all_records() -> None:
    call_command("load_wc2026", verbosity=0)
    assert Team.objects.count() == 48
    assert Match.objects.filter(stage=Match.Stage.GROUP).count() == 72
    for letter in "ABCDEFGHIJKL":
        assert TournamentTeam.objects.filter(group_letter=letter).count() == 4, (
            f"Group {letter} should have 4 teams"
        )


@pytest.mark.django_db
def test_load_wc2026_is_idempotent() -> None:
    call_command("load_wc2026", verbosity=0)
    call_command("load_wc2026", verbosity=0)
    assert Team.objects.count() == 48
    assert Match.objects.filter(stage=Match.Stage.GROUP).count() == 72
