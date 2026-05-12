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
