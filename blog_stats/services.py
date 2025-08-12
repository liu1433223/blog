import json
import logging
from django.core.cache import cache
from django_redis import get_redis_connection

from blog_stats.models import UserRead

logger = logging.getLogger(__name__)


class StatsCacheService:
    @staticmethod
    def get_user_read_count(article_id, user_id):
        cache_key = f"article:{article_id}:user:{user_id}"
        value = cache.get(cache_key)
        if value is not None:
            return int(value)

        # 如果缓存未命中，从数据库中查询
        try:
            user_read = UserRead.objects.filter(article_id=article_id, user_id=user_id).first()
            read_count = user_read.read_count if user_read else 0
            # 将结果回填到缓存
            cache.set(cache_key, read_count, timeout=3600)  # 缓存1小时
            return read_count
        except Exception as e:
            logger.error(f"Failed to get user read count for article {article_id}, user {user_id}: {str(e)}")
            return 0

    @staticmethod
    def get_total_reads(article_id):
        """获取文章总阅读量"""
        key = f"article:{article_id}:total_reads"
        value = cache.get(key)
        if value is not None:
            return int(value)
        return None

    @staticmethod
    def get_user_count(article_id):
        """获取阅读用户数"""
        key = f"article:{article_id}:user_count"
        value = cache.get(key)
        if value is not None:
            return int(value)
        return None

    @staticmethod
    def increment_read(article_id, user_id):
        """增加阅读计数"""
        redis_conn = get_redis_connection("default")

        # 使用管道确保原子性操作
        with redis_conn.pipeline() as pipe:
            # 用户阅读记录
            user_key = f"article:{article_id}:user:{user_id}"
            pipe.incr(user_key)

            # 总阅读量
            total_key = f"article:{article_id}:total_reads"
            pipe.incr(total_key)

            # 检查是否新用户
            if not redis_conn.exists(user_key):
                user_count_key = f"article:{article_id}:user_count"
                pipe.incr(user_count_key)
                pipe.expire(user_key, 86400)  # 24小时过期

            # 执行所有命令
            pipe.execute()

        # 添加异步更新任务
        from .tasks import async_update_stats
        async_update_stats.delay(article_id, user_id)

    @staticmethod
    def get_cache_hit_rate():
        """获取缓存命中率"""
        redis_conn = get_redis_connection("default")
        hits = redis_conn.get("cache:hits") or 0
        misses = redis_conn.get("cache:misses") or 0
        total = int(hits) + int(misses)
        return (int(hits) / total * 100) if total > 0 else 0


    @staticmethod
    def get_total_reads_all_articles():
        """从缓存中获取所有文章的总阅读量"""
        redis_conn = get_redis_connection("default")
        value = redis_conn.get("total_reads_all")
        return int(value) if value else None

    @staticmethod
    def cache_total_reads_all_articles(total_reads):
        """将所有文章的总阅读量存入缓存"""
        redis_conn = get_redis_connection("default")
        redis_conn.set("total_reads_all", total_reads, ex=3600)