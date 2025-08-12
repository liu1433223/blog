# blog_stats/test_middleware.py
import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from blog_stats.middleware import TrackArticleReadMiddleware
from unittest.mock import MagicMock, patch


@pytest.mark.django_db
class TestTrackArticleReadMiddleware:
    @pytest.fixture
    def middleware(self):
        def get_response(request):
            return MagicMock(status_code=200)

        return TrackArticleReadMiddleware(get_response)

    def test_middleware_article_page(self, middleware):
        factory = RequestFactory()
        request = factory.get('/blog/article/123/')

        # Mock resolver_match
        class MockResolverMatch:
            kwargs = {'article_id': 123}

        request.resolver_match = MockResolverMatch()

        # 正确设置session
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()

        # Mock服务调用以避免实际的Redis连接
        with patch('blog_stats.middleware.StatsCacheService.increment_read') as mock_increment:
            middleware(request)

            # 验证阅读统计被触发
            assert hasattr(request, '_read_tracked')
            assert request._read_tracked == True
            mock_increment.assert_called_once_with(123, request.session.session_key)

    def test_middleware_non_article_page(self, middleware):
        factory = RequestFactory()
        request = factory.get('/blog/categories/')

        # Mock resolver_match
        request.resolver_match = None

        middleware(request)

        # 验证阅读统计未触发
        assert not hasattr(request, '_read_tracked')

    def test_middleware_error_response(self, middleware):
        factory = RequestFactory()
        request = factory.get('/blog/article/123/')

        # Mock resolver_match
        class MockResolverMatch:
            kwargs = {'article_id': 123}

        request.resolver_match = MockResolverMatch()

        # 模拟错误响应
        def get_response(req):
            return MagicMock(status_code=404)

        middleware.get_response = get_response

        middleware(request)

        assert not hasattr(request, '_read_tracked')
