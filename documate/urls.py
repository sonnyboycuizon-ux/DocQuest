from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as django_serve
import os


def secure_media_serve(request, path, document_root=None):
    """Serve media files; works even when DEBUG=False for local/dev environments.
       For uploaded profile images, ensure correct Content-Type even for .jfif."""
    import mimetypes
    from django.http import FileResponse, Http404

    if not request.user.is_authenticated:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Authentication required')

    document_root = document_root or settings.MEDIA_ROOT
    full_path = os.path.normpath(os.path.join(document_root, path))

    if not full_path.startswith(os.path.normpath(document_root)):
        raise Http404('Path outside media root')

    if not os.path.isfile(full_path):
        raise Http404(f'Media file not found: {path}')

    content_type, _ = mimetypes.guess_type(full_path)
    lower = full_path.lower()
    if not content_type:
        if lower.endswith('.jfif'):
            content_type = 'image/jpeg'
        elif lower.endswith('.webp'):
            content_type = 'image/webp'
        else:
            content_type = 'application/octet-stream'
    elif lower.endswith('.jfif') and content_type != 'image/jpeg':
        content_type = 'image/jpeg'

    response = FileResponse(open(full_path, 'rb'), content_type=content_type)
    response['Content-Length'] = os.path.getsize(full_path)
    return response


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('login')),
    path('', include('requestsystem.urls')),
    path('media/<path:path>', secure_media_serve, {'document_root': settings.MEDIA_ROOT}, name='serve_media'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
