from django.views import View
from django.http import JsonResponse
from django.views.generic import TemplateView

from .services import StatsCacheService
from .models import ArticleStats, UserRead


import logging

logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    template_name = 'stats_monitor.html'

class TrackArticleReadView(View):
    """跟踪文章阅读"""

    def post(self, request, article_id):
        user_id = self.get_user_id(request)

        try:
            StatsCacheService.increment_read(article_id, user_id)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Tracking error: {str(e)}")
            # 降级处理：直接更新数据库
            self.update_directly(article_id, user_id)
            return JsonResponse({'status': 'degraded', 'message': str(e)}, status=500)

    def get_user_id(self, request):
        """获取用户标识"""
        if request.user.is_authenticated:
            return str(request.user.id)
        return request.session.session_key or request.META.get('REMOTE_ADDR', 'anonymous')

    def update_directly(self, article_id, user_id):
        """直接更新数据库（降级方案）"""
        try:
            # 简化版直接更新
            article_stats, _ = ArticleStats.objects.get_or_create(
                article_id=article_id,
                defaults={'total_reads': 0, 'user_count': 0}
            )
            article_stats.total_reads += 1
            article_stats.save()

            # 更新用户阅读记录
            UserRead.objects.update_or_create(
                article_id=article_id,
                user_id=user_id,
                defaults={'read_count': 1}
            )
        except Exception as e:
            logger.critical(f"Direct update failed: {str(e)}")


class ArticleStatsView(View):
    """获取文章统计数据"""

    def get(self, request, article_id):
        try:
            total_reads = StatsCacheService.get_total_reads(article_id)
            user_count = StatsCacheService.get_user_count(article_id)

            # 缓存命中率统计
            redis_conn = get_redis_connection("default")
            if total_reads is not None and user_count is not None:
                redis_conn.incr("cache:hits")
                return JsonResponse({
                    'article_id': article_id,
                    'total_reads': total_reads,
                    'user_count': user_count,
                    'source': 'cache'
                })
            else:
                redis_conn.incr("cache:misses")
                # 缓存未命中，查询数据库
                try:
                    stats = ArticleStats.objects.get(article_id=article_id)
                    # 回填缓存
                    StatsCacheService.cache_stats(article_id, stats.total_reads, stats.user_count)
                    return JsonResponse({
                        'article_id': article_id,
                        'total_reads': stats.total_reads,
                        'user_count': stats.user_count,
                        'source': 'database'
                    })
                except ArticleStats.DoesNotExist:
                    return JsonResponse({
                        'article_id': article_id,
                        'total_reads': 0,
                        'user_count': 0,
                        'source': 'default'
                    })
        except Exception as e:
            logger.error(f"Stats retrieval error: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error',
                'article_id': article_id
            }, status=500)


class CacheStatsView(View):
    """获取缓存统计信息"""

    def get(self, request):
        try:
            hit_rate = StatsCacheService.get_cache_hit_rate()
            redis_conn = get_redis_connection("default")
            keys = redis_conn.info('keyspace')

            return JsonResponse({
                'hit_rate': f"{hit_rate:.2f}%",
                'redis_stats': keys,
                'total_keys': redis_conn.dbsize()
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)