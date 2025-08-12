import os
from django.conf import settings
from django.core.files.storage import default_storage
from ...utils.paths import product_media_upload_path
import mimetypes


def save_product_file(store_slug, product_slug, uploaded_file):
    path = product_media_upload_path(store_slug, product_slug, uploaded_file.name)
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    # Determinar tipo de archivo
    mime_type, _ = mimetypes.guess_type(uploaded_file.name)
    if mime_type and mime_type.startswith('video'):
        file_type = 'video'
    else:
        file_type = 'image'

    return {
        "url": os.path.join(settings.MEDIA_URL, path),
        "type": file_type
    }
