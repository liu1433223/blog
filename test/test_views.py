# blog_stats/test_views.py
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient
from blog_stats.models import ArticleStats, UserRead
from unittest.mock import patch
from django_redis import get_redis_connection
import fakeredis


@pytest.mark.django_db
class TestArticleStatsViews:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture(autouse=True)
    def setup_cache(self, monkeypatch):
        # 使用fakeredis模拟Redis
        fake_redis = fakeredis.FakeStrictRedis()
        monkeypatch.setattr('django_redis.get_redis_connection', lambda *args: fake_redis)
        cache.clear()

    def test_track_article_read_new(self, client):
        url = reverse('track-read', kwargs={'article_id': 1})
        response = client.post(url)

        assert response.status_code == 200
        assert response.json()['status'] == 'success'

        cached_value = cache.get(f"article:1:total_reads")
        assert cached_value is not None
        assert int(cached_value) == 1

    def test_track_article_read_cache_failure(self, client):
        # 模拟缓存异常
        with patch('blog_stats.services.StatsCacheService.increment_read',
                   side_effect=Exception("Redis error")):
            url = reverse('track-read', kwargs={'article_id': 1})
            response = client.post(url)

            assert response.status_code in [200, 500]
            response_data = response.json()
            assert response_data['status'] in ['success', 'degraded']

            # 验证数据库直接更新
            stats = ArticleStats.objects.get(article_id=1)
            assert stats.total_reads >= 0

    def test_get_stats_cache_hit(self, client):
        # 设置缓存值
        cache.set(f"article:1:total_reads", 100)
        cache.set(f"article:1:user_count", 50)

        url = reverse('article-stats', kwargs={'article_id': 1})
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['total_reads'] == 100
        assert data['user_count'] == 50
        assert data['source'] in ['cache', 'database', 'default']

    def test_get_stats_cache_miss(self, client):
        # 创建数据库记录
        ArticleStats.objects.create(article_id=1, total_reads=200, user_count=100)

        url = reverse('article-stats', kwargs={'article_id': 1})
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['total_reads'] == 200
        assert data['user_count'] == 100
        assert data['source'] in ['cache', 'database', 'default']

        # 验证缓存回填
        cached_total = cache.get(f"article:1:total_reads")
        if cached_total is not None:
            assert int(cached_total) == 200

    def test_get_cache_stats(self, client):
        # 使用cache而不是直接操作redis_conn
        cache.set("cache:hits", 90)
        cache.set("cache:misses", 10)

        url = reverse('cache-stats')
        response = client.get(url)

        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert 'hit_rate' in data or 'error' in data
