# views/post/media_upload.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from ...connection import mongo_db
 # Reutiliza el de productos si aplica
import os
import mimetypes
from bson import ObjectId
from django.conf import settings
from django.core.files.storage import default_storage
from ...utils.paths import post_media_upload_path

posts_collection = mongo_db["post"]

def save_post_file(request, store_slug, post_id, uploaded_file):
    # Construir la ruta de guardado
    path = post_media_upload_path(store_slug, post_id, uploaded_file.name)
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    # Guardar el archivo
    with open(full_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    # Determinar tipo (imagen o video)
    mime_type, _ = mimetypes.guess_type(uploaded_file.name)
    file_type = 'video' if mime_type and mime_type.startswith('video') else 'image'
    
    # Aquí creas la URL absoluta
    relative_url = os.path.join(settings.MEDIA_URL, path).replace("\\", "/")  # Asegura formato web

    return {
        "url": relative_url,
        "type": file_type,
        "name": uploaded_file.name,
        "size": uploaded_file.size,
        "content_type": uploaded_file.content_type
    }

