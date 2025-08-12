# blog_stats/test_services.py
from unittest.mock import patch, MagicMock
import pytest
from blog_stats.services import StatsCacheService
from django.core.cache import cache
from django_redis import get_redis_connection
import fakeredis


@pytest.fixture(autouse=True)
def setup_cache(monkeypatch):
    # 使用fakeredis模拟Redis
    fake_redis = fakeredis.FakeStrictRedis()
    monkeypatch.setattr('django_redis.get_redis_connection', lambda *args: fake_redis)
    cache.clear()


class TestStatsCacheService:
    def test_increment_read_new_user(self):
        article_id = 1
        user_id = "user1"

        StatsCacheService.increment_read(article_id, user_id)

        # 验证总阅读量
        total_key = f"article:{article_id}:total_reads"
        total_value = cache.get(total_key)
        assert total_value is not None and int(total_value) == 1

        # 验证用户阅读记录
        user_key = f"article:{article_id}:user:{user_id}"
        user_value = cache.get(user_key)
        assert user_value is not None and int(user_value) == 1

        # 验证用户数
        user_count_key = f"article:{article_id}:user_count"
        user_count_value = cache.get(user_count_key)
        assert user_count_value is not None and int(user_count_value) == 1

    def test_increment_read_existing_user(self):
        article_id = 1
        user_id = "user1"

        # 第一次阅读
        StatsCacheService.increment_read(article_id, user_id)
        # 第二次阅读
        StatsCacheService.increment_read(article_id, user_id)

        total_key = f"article:{article_id}:total_reads"
        total_value = cache.get(total_key)
        assert total_value is not None and int(total_value) == 2

        user_key = f"article:{article_id}:user:{user_id}"
        user_value = cache.get(user_key)
        assert user_value is not None and int(user_value) == 2

        user_count_key = f"article:{article_id}:user_count"
        user_count_value = cache.get(user_count_key)
        assert user_count_value is not None and int(user_count_value) == 1  # 用户数不应增加

    def test_get_total_reads(self):
        article_id = 1
        cache.set(f"article:{article_id}:total_reads", 100)
        assert StatsCacheService.get_total_reads(article_id) == 100

    def test_get_user_count(self):
        article_id = 1
        cache.set(f"article:{article_id}:user_count", 50)
        assert StatsCacheService.get_user_count(article_id) == 50

    @patch('blog_stats.services.logger')
    @pytest.mark.django_db
    def test_increment_read_cache_failure(self, mock_logger):
        # 模拟cache方法异常
        with patch('django.core.cache.cache.get', side_effect=Exception("Cache error")):
            article_id = 1
            user_id = "user1"

            # 应触发降级逻辑
            StatsCacheService.increment_read(article_id, user_id)

            # 验证日志记录
            mock_logger.error.assert_called()
            assert mock_logger.error.call_count >= 1

    def test_cache_hit_rate_calculation(self):
        # 设置初始命中率
        cache.set("cache:hits", 80)
        cache.set("cache:misses", 20)

        hit_rate = StatsCacheService.get_cache_hit_rate()
        assert hit_rate == 80.0  # 80/(80+20)=80%
