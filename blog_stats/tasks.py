from celery import shared_task
from django.db import transaction
from .models import ArticleStats, UserRead
from .services import StatsCacheService
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def async_update_stats(self, article_id, user_id):
    try:
        with transaction.atomic():
            # 更新用户阅读记录
            user_read, created = UserRead.objects.update_or_create(
                article_id=article_id,
                user_id=user_id,
                defaults={
                    'read_count': StatsCacheService.get_user_read_count(article_id, user_id)
                }
            )

            # 更新文章统计
            article_stats, created = ArticleStats.objects.get_or_create(
                article_id=article_id,
                defaults={
                    'total_reads': StatsCacheService.get_total_reads(article_id),
                    'user_count': StatsCacheService.get_user_count(article_id)
                }
            )

            if not created:
                article_stats.total_reads = StatsCacheService.get_total_reads(article_id)
                article_stats.user_count = StatsCacheService.get_user_count(article_id)
                article_stats.save()

    except Exception as e:
        logger.error(f"Async update failed: {str(e)}")
        self.retry(exc=e, countdown=2 ** self.request.retries)