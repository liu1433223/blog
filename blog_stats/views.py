# blog_stats/views.py
from django.db.models import Sum
from django.views import View
from django.http import JsonResponse
from django.views.generic import TemplateView

from .services import StatsCacheService
from .models import ArticleStats, UserRead
from django_redis import get_redis_connection

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

            # 新增：获取每个用户的阅读次数分布
            user_read_distribution = self.get_user_read_distribution(article_id)

            # 缓存命中率统计
            redis_conn = get_redis_connection("default")
            if total_reads is not None and user_count is not None:
                redis_conn.incr("cache:hits")
                return JsonResponse({
                    'article_id': article_id,
                    'total_reads': total_reads,
                    'user_count': user_count,
                    'user_read_distribution': user_read_distribution,
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
                        'user_read_distribution': user_read_distribution,
                        'source': 'database'
                    })
                except ArticleStats.DoesNotExist:
                    return JsonResponse({
                        'article_id': article_id,
                        'total_reads': 0,
                        'user_count': 0,
                        'user_read_distribution': {},
                        'source': 'default'
                    })
        except Exception as e:
            logger.error(f"Stats retrieval error: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error',
                'article_id': article_id
            }, status=500)

    def get_user_read_distribution(self, article_id):
        """获取每个用户的阅读次数分布"""
        user_reads = UserRead.objects.filter(article_id=article_id).values('user_id', 'read_count')
        return {str(item['user_id']): item['read_count'] for item in user_reads}


class CacheStatsView(View):
    """获取缓存统计信息"""

    def get(self, request):
        try:
            hit_rate = StatsCacheService.get_cache_hit_rate()
            redis_conn = get_redis_connection("default")
            keys = redis_conn.info('keyspace')

            # 获取热门文章
            top_articles = StatsCacheService.get_top_articles()
            # 转换为前端需要的格式
            top_articles_data = []
            for article in top_articles:
                top_articles_data.append({
                    'title': f'Article {article.article_id}',
                    'reads': article.total_reads
                })

            return JsonResponse({
                'hit_rate': f"{hit_rate:.2f}%",
                'redis_stats': keys,
                'total_keys': redis_conn.dbsize(),
                'top_articles': top_articles_data  # 提供文章数据而不是数量
            })
        except Exception as e:
            logger.error(f"Cache stats error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class TotalReadsView(View):
    """获取所有文章的总阅读量"""

    def get(self, request):
        try:
            # 从缓存中获取总阅读量
            total_reads = StatsCacheService.get_total_reads_all_articles()

            if total_reads is None:
                # 如果缓存未命中，从数据库中计算总阅读量
                result = ArticleStats.objects.aggregate(total=Sum('total_reads'))
                total_reads = result['total'] or 0
                # 将结果回填到缓存
                StatsCacheService.cache_total_reads_all_articles(total_reads)

            # 统计所有文章的用户人次
            total_users = UserRead.objects.values('user_id').distinct().count()

            # 获取用户阅读分布
            user_read_distribution = self.get_user_read_distribution()

            return JsonResponse({
                'total_reads': total_reads,
                'total_users': total_users,
                'user_read_distribution': user_read_distribution,  # 提供分布数据而不是数量
                'source': 'cache' if total_reads is not None else 'database'
            })
        except Exception as e:
            logger.error(f"Total reads retrieval error: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)

    def get_user_read_distribution(self):
        """获取每个用户的阅读次数分布"""
        user_reads = UserRead.objects.values('user_id', 'read_count')
        return {str(item['user_id']): item['read_count'] for item in user_reads}
