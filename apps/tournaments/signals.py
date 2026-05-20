from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Match


@receiver(post_save, sender=Match)
def on_match_saved(sender, instance: Match, **kwargs) -> None:
    if (
        instance.home_score is not None
        and instance.away_score is not None
        and instance.status == Match.Status.COMPLETED
    ):
        try:
            from apps.leaderboard.tasks import recalculate_pool_scores  # noqa: PLC0415
            recalculate_pool_scores.delay(instance.pk)
        except ImportError:
            pass
