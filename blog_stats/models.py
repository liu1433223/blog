from django.db import models
from django.utils import timezone


class ArticleStats(models.Model):
    article_id = models.BigIntegerField(
        primary_key=True,
        verbose_name="文章ID"
    )
    total_reads = models.PositiveIntegerField(
        default=0,
        verbose_name="总阅读量"
    )
    user_count = models.PositiveIntegerField(
        default=0,
        verbose_name="用户数量"
    )
    last_updated = models.DateTimeField(
        default=timezone.now,
        verbose_name="最后更新时间"
    )


class UserRead(models.Model):
    article = models.ForeignKey(
        ArticleStats,
        on_delete=models.CASCADE,
        verbose_name="所属文章"
    )
    user_id = models.CharField(
        max_length=128,
        verbose_name="用户ID"
    )
    read_count = models.PositiveIntegerField(
        default=1,
        verbose_name="阅读次数"
    )
    last_read = models.DateTimeField(
        default=timezone.now,
        verbose_name="最后阅读时间"
    )

    class Meta:
        unique_together = ('article', 'user_id')
