# blog_stats/middleware.py
from django.utils.deprecation import MiddlewareMixin
from .services import StatsCacheService
import re


class TrackArticleReadMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    def __call__(self, request):
        response = self.get_response(request)

        # 检查是否是文章页面且响应成功
        if (response.status_code == 200 and
                hasattr(request, 'resolver_match') and
                request.resolver_match and
                re.match(r'^/blog/article/\d+/', request.path)):
            article_id = request.resolver_match.kwargs.get('article_id')
            if article_id and not getattr(request, '_read_tracked', False):
                user_id = self.get_user_id(request)
                try:
                    StatsCacheService.increment_read(article_id, user_id)
                    request._read_tracked = True
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to track read for article {article_id}: {str(e)}")

        return response

    def get_user_id(self, request):
        """获取用户标识"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return str(request.user.id)
        return request.session.session_key or request.META.get('REMOTE_ADDR', 'anonymous')
