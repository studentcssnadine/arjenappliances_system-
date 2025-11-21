"""
URL configuration for ArjenSystem project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from myapp.sitemaps import StaticViewSitemap
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('myapp.urls')),
]

# Google site verification file route
urlpatterns += [
    path(
        'googlede1306614c3affbb.html',
        TemplateView.as_view(template_name='googlede1306614c3affbb.html'),
        name='google-site-verification'
    ),
]

# robots.txt route
urlpatterns += [
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain")
    ),
]

# Sitemap configuration
sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns += [
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
