# blog_stats/test_tasks.py
from unittest.mock import patch

import pytest

from blog_stats.models import ArticleStats, UserRead
from blog_stats.tasks import async_update_stats


@pytest.fixture
def cache():
    from django.core.cache import cache
    cache.clear()
    return cache

@pytest.mark.django_db
class TestAsyncUpdateStats:
    def test_new_article_update(self, cache):
        article_id = 1
        user_id = "user1"

        # 创建文章记录以避免外键约束错误
        ArticleStats.objects.create(article_id=article_id, total_reads=0, user_count=0)

        # 设置缓存值
        cache.set(f"article:{article_id}:total_reads", 5)
        cache.set(f"article:{article_id}:user_count", 3)
        cache.set(f"article:{article_id}:user:{user_id}", 1)

        # 执行异步任务
        async_update_stats(article_id, user_id)

        # 验证数据库更新
        stats = ArticleStats.objects.get(article_id=article_id)
        assert stats.total_reads == 5
        assert stats.user_count == 3

        # 验证用户阅读记录
        user_read = UserRead.objects.get(article_id=article_id, user_id=user_id)
        assert user_read.read_count >= 1

    def test_existing_article_update(self, cache):
        article_id = 1
        user_id = "user1"

        # 创建初始记录
        ArticleStats.objects.create(article_id=article_id, total_reads=10, user_count=2)
        UserRead.objects.create(article_id=article_id, user_id=user_id, read_count=3)

        # 设置新的缓存值
        cache.set(f"article:{article_id}:total_reads", 15)
        cache.set(f"article:{article_id}:user_count", 3)
        cache.set(f"article:{article_id}:user:{user_id}", 4)

        # 执行异步任务
        async_update_stats(article_id, user_id)

        # 验证数据库更新
        stats = ArticleStats.objects.get(article_id=article_id)
        assert stats.total_reads == 15
        assert stats.user_count == 3

        # 验证用户阅读记录更新
        user_read = UserRead.objects.get(article_id=article_id, user_id=user_id)
        assert user_read.read_count == 4

    @patch('blog_stats.tasks.logger')
    def test_task_retry_on_failure(self, mock_logger):
        # 模拟数据库错误
        with patch('blog_stats.models.ArticleStats.objects.get_or_create',
                   side_effect=Exception("DB error")):
            article_id = 1
            user_id = "user1"

            # 执行异步任务并捕获重试
            try:
                async_update_stats(article_id, user_id)
            except Exception:
                pass

            # 重试
            mock_logger.error.assert_called()
            assert mock_logger.error.call_count >= 1
