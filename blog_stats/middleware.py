class TrackArticleReadMiddleware:
    """自动跟踪文章阅读的中间件"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 如果是文章详情页且请求成功
        if response.status_code == 200 and 'blog/article' in request.path:
            article_id = self.extract_article_id(request.path)
            if article_id:
                from .views import TrackArticleReadView
                tracker = TrackArticleReadView()
                tracker.post(request, article_id)

        return response

    def extract_article_id(self, path):
        """从URL中提取文章ID"""
        try:
            # 假设URL格式为 /blog/article/<id>/
            parts = path.split('/')
            if len(parts) > 3 and parts[-2].isdigit():
                return int(parts[-2])
        except:
            return None
        return None