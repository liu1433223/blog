# blog_stats/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('track/<int:article_id>/', views.TrackArticleReadView.as_view(), name='track-read'),
    path('stats/<int:article_id>/', views.ArticleStatsView.as_view(), name='article-stats'),
    path('stats/cache-stats/', views.CacheStatsView.as_view(), name='cache-stats'),
    path('stats/total-reads/', views.TotalReadsView.as_view(), name='total-reads'),  # 新增路由

]
