import itertools
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.tournaments.models import Match, Team, Tournament, TournamentTeam


class Command(BaseCommand):
    help = "Load 2026 FIFA World Cup data from data/wc2026.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tournament-slug",
            default="wc2026",
            help="Slug of the tournament to load (default: wc2026)",
        )

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[4] / "data" / "wc2026.json"
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

        # Matches — generate round-robin for each group
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

        total_matches = Match.objects.filter(
            tournament=tournament, stage=Match.Stage.GROUP
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {match_count} new matches created. Total group matches: {total_matches}"
            )
        )
