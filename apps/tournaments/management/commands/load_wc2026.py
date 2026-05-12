import itertools
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.tournaments.models import Match, Team, Tournament, TournamentTeam

DATA_DIR = Path(__file__).resolve().parents[4] / "data"

BRACKET_STAGE_MAP = {
    "r32": Match.Stage.R32,
    "r16": Match.Stage.R16,
    "qf": Match.Stage.QF,
    "sf": Match.Stage.SF,
    "final": Match.Stage.FINAL,
}


class Command(BaseCommand):
    help = "Load 2026 FIFA World Cup data from data/wc2026.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tournament-slug",
            default="wc2026",
            help="Slug of the tournament to load (default: wc2026)",
        )

    def handle(self, *args, **options):
        fixture_path = DATA_DIR / "wc2026.json"
        with fixture_path.open() as f:
            data = json.load(f)

        # Tournament
        t_data = data["tournament"]
        tournament, created = Tournament.objects.get_or_create(
            slug=options["tournament_slug"],
            defaults={
                "name": t_data["name"],
                "num_groups": t_data["num_groups"],
                "teams_per_group": t_data["teams_per_group"],
                "third_place_advancers": t_data["third_place_advancers"],
                "scoring_config": t_data["scoring_config"],
            },
        )
        action = "Created" if created else "Found"
        self.stdout.write(f"{action} tournament: {tournament}")

        # Teams
        teams_by_code: dict[str, Team] = {}
        for t in data["teams"]:
            team, created = Team.objects.get_or_create(
                fifa_code=t["fifa_code"],
                defaults={"name": t["name"], "flag_url": t.get("flag_url", "")},
            )
            teams_by_code[t["fifa_code"]] = team
            action = "Created" if created else "Found"
            self.stdout.write(f"  {action} team: {team}")

        # Groups → TournamentTeams
        ranking_map = {t["fifa_code"]: t["fifa_ranking"] for t in data["teams"]}
        for group_letter, codes in data["groups"].items():
            for code in codes:
                team = teams_by_code[code]
                tt, created = TournamentTeam.objects.get_or_create(
                    tournament=tournament,
                    team=team,
                    defaults={
                        "group_letter": group_letter,
                        "fifa_ranking": ranking_map[code],
                    },
                )
                if not created and tt.group_letter != group_letter:
                    tt.group_letter = group_letter
                    tt.save()

        self.stdout.write(
            f"Loaded {TournamentTeam.objects.filter(tournament=tournament).count()} TournamentTeams"
        )

        # Group matches — generate round-robin for each group
        match_count = 0
        for group_letter, codes in data["groups"].items():
            group_teams = [teams_by_code[c] for c in codes]
            for home_team, away_team in itertools.combinations(group_teams, 2):
                _, created = Match.objects.get_or_create(
                    tournament=tournament,
                    stage=Match.Stage.GROUP,
                    group_letter=group_letter,
                    home_team=home_team,
                    away_team=away_team,
                )
                if created:
                    match_count += 1

        total_group = Match.objects.filter(tournament=tournament, stage=Match.Stage.GROUP).count()
        self.stdout.write(f"{match_count} new group matches created. Total: {total_group}")

        # Knockout placeholder matches — one per bracket slot
        bracket_path = DATA_DIR / "knockout_bracket.json"
        with bracket_path.open() as f:
            bracket_data = json.load(f)

        ko_count = 0
        for stage_key, slots in bracket_data.items():
            if stage_key.startswith("_"):
                continue
            stage = BRACKET_STAGE_MAP.get(stage_key)
            if stage is None:
                continue
            for slot_def in slots:
                _, created = Match.objects.get_or_create(
                    tournament=tournament,
                    stage=stage,
                    bracket_slot=slot_def["slot"],
                    defaults={"home_team": None, "away_team": None},
                )
                if created:
                    ko_count += 1

        total_ko = Match.objects.filter(tournament=tournament).exclude(stage=Match.Stage.GROUP).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {ko_count} new knockout matches created. Total knockout placeholders: {total_ko}"
            )
        )
