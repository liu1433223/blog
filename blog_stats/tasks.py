# blog_stats/tasks.py
from celery import shared_task
from .models import ArticleStats, UserRead
from .services import StatsCacheService
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def async_update_stats(self, article_id, user_id):
    try:
        # 从缓存获取最新数据
        total_reads = StatsCacheService.get_total_reads(article_id)
        user_count = StatsCacheService.get_user_count(article_id)

        # 更新数据库
        article_stats, created = ArticleStats.objects.get_or_create(
            article_id=article_id,
            defaults={
                'total_reads': total_reads or 0,
                'user_count': user_count or 0
            }
        )

        if not created:
            if total_reads is not None:
                article_stats.total_reads = total_reads
            if user_count is not None:
                article_stats.user_count = user_count
            article_stats.save()

        # 更新用户阅读记录
        user_read, created = UserRead.objects.get_or_create(
            article_id=article_id,
            user_id=user_id,
            defaults={'read_count': 0}
        )

        # 获取特定用户的阅读次数
        user_read_count = StatsCacheService.get_user_read_count(article_id, user_id)
        if user_read_count is not None:
            user_read.read_count = user_read_count
        else:
            user_read.read_count += 1

        user_read.save()

    except Exception as exc:
        logger.error(f"Failed to update stats for article {article_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)
