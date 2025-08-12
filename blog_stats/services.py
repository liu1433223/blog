# blog_stats/services.py
from django.core.cache import cache
# from django_redis import get_redis_connection
import logging

logger = logging.getLogger(__name__)


class StatsCacheService:
    @staticmethod
    def increment_read(article_id, user_id):
        """增加文章阅读次数"""
        try:
            # 使用Django cache接口而不是直接操作Redis
            # 增加总阅读量
            total_reads_key = f"article:{article_id}:total_reads"
            total_reads = cache.get(total_reads_key)
            if total_reads is None:
                total_reads = 0
            cache.set(total_reads_key, total_reads + 1, timeout=3600)

            # 记录用户阅读
            user_key = f"article:{article_id}:user:{user_id}"
            user_read_count = cache.get(user_key)
            user_existed = user_read_count is not None

            if user_read_count is None:
                user_read_count = 0
            cache.set(user_key, user_read_count + 1, timeout=3600)

            # 如果是新用户，增加用户数
            user_count_key = f"article:{article_id}:user_count"
            user_count = cache.get(user_count_key)
            if user_count is None:
                user_count = 0

            if not user_existed:
                cache.set(user_count_key, user_count + 1, timeout=3600)

        except Exception as e:
            logger.error(f"Cache unavailable, using DB fallback: {str(e)}")
            # 降级到数据库处理
            from .models import ArticleStats, UserRead

            article_stats, _ = ArticleStats.objects.get_or_create(
                article_id=article_id,
                defaults={'total_reads': 0, 'user_count': 0}
            )

            article_stats.total_reads += 1

            # 检查是否为新用户
            user_read, created = UserRead.objects.get_or_create(
                article_id=article_id,
                user_id=user_id,
                defaults={'read_count': 0}
            )

            if created:
                article_stats.user_count += 1

            user_read.read_count += 1
            user_read.save()
            article_stats.save()

    @staticmethod
    def get_total_reads(article_id):
        """获取文章总阅读量"""
        key = f"article:{article_id}:total_reads"
        value = cache.get(key)
        return int(value) if value is not None else None

    @staticmethod
    def get_user_count(article_id):
        """获取文章用户数"""
        key = f"article:{article_id}:user_count"
        value = cache.get(key)
        return int(value) if value is not None else None

    @staticmethod
    def cache_stats(article_id, total_reads, user_count):
        """缓存文章统计数据"""
        cache.set(f"article:{article_id}:total_reads", total_reads, timeout=3600)
        cache.set(f"article:{article_id}:user_count", user_count, timeout=3600)

    @staticmethod
    def get_cache_hit_rate():
        """获取缓存命中率"""
        try:
            hits = cache.get("cache:hits") or 0
            misses = cache.get("cache:misses") or 0
            hits = int(hits)
            misses = int(misses)
            total = hits + misses
            if total == 0:
                return 0.0
            return (hits / total) * 100
        except Exception:
            return 0.0

    @staticmethod
    def get_total_reads_all_articles():
        """获取所有文章总阅读量"""
        key = "total_reads_all_articles"
        value = cache.get(key)
        return int(value) if value is not None else None

    @staticmethod
    def cache_total_reads_all_articles(total_reads):
        """缓存所有文章总阅读量"""
        cache.set("total_reads_all_articles", total_reads, timeout=3600)

    @staticmethod
    def get_top_articles():
        """获取热门文章"""
        from .models import ArticleStats
        try:
            # 获取阅读量大于0的文章，按阅读量排序，取前10篇
            top_articles = ArticleStats.objects.filter(total_reads__gt=0).order_by('-total_reads')[:10]
            return list(top_articles)
        except Exception:
            return []

    @staticmethod
    def get_user_read_count(article_id, user_id):
        """获取特定用户对文章的阅读次数"""
        key = f"article:{article_id}:user:{user_id}"
        value = cache.get(key)
        return int(value) if value is not None else None

