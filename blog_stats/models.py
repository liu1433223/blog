from django.db import models
from django.utils import timezone

class ArticleStats(models.Model):
    article_id = models.BigIntegerField(primary_key=True)
    total_reads = models.PositiveIntegerField(default=0)
    user_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(default=timezone.now)

class UserRead(models.Model):
    article = models.ForeignKey(ArticleStats, on_delete=models.CASCADE)
    user_id = models.CharField(max_length=128)
    read_count = models.PositiveIntegerField(default=1)
    last_read = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('article', 'user_id')
