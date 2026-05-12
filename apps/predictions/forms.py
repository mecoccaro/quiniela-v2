from django import forms


class MatchPredictionForm(forms.Form):
    predicted_home_score = forms.IntegerField(min_value=0, max_value=20)
    predicted_away_score = forms.IntegerField(min_value=0, max_value=20)

    def clean(self) -> dict:
        data = super().clean() or {}
        home = data.get("predicted_home_score")
        away = data.get("predicted_away_score")
        if (home is None) != (away is None):
            raise forms.ValidationError("Both scores must be provided together.")
        return data


class KnockoutPredictionForm(forms.Form):
    predicted_home_score = forms.IntegerField(min_value=0, max_value=20)
    predicted_away_score = forms.IntegerField(min_value=0, max_value=20)
    predicted_winner = forms.IntegerField(required=False)

    def clean(self) -> dict:
        data = super().clean() or {}
        home = data.get("predicted_home_score")
        away = data.get("predicted_away_score")
        winner = data.get("predicted_winner")
        if home is not None and away is not None and home == away and not winner:
            raise forms.ValidationError(
                "Tenés que elegir un ganador cuando el resultado es empate."
            )
        return data


class ChampionPickForm(forms.Form):
    team_id = forms.IntegerField()


class TopScorerPickForm(forms.Form):
    player_name = forms.CharField(max_length=100, strip=True)
