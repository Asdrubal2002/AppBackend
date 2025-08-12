from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
import secrets
import string
import uuid
import os
from django.utils.text import slugify


def safe_filename(original_name):
    name, ext = os.path.splitext(original_name)
    slug = slugify(name)  # e.g. "Empire Of The Sun" => "empire-of-the-sun"
    unique = uuid.uuid4().hex[:8]
    return f"{slug}-{unique}{ext}"


def compress_image(file, max_size=1024, quality=75):
    img = Image.open(file)
    original_format = img.format  # 'PNG', 'JPEG', etc.
    img = img.convert('RGB')

    # Redimensionar si excede tamaño
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    # Si es PNG pequeño, devuélvelo tal cual
    if original_format == 'PNG' and file.size < 100 * 1024:
        file.seek(0)
        return file, file.name

    # Comprimir a JPEG
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=quality)
    buffer.seek(0)
    new_name = file.name.rsplit('.', 1)[0] + '_compressed.jpg'
    compressed_file = InMemoryUploadedFile(
        buffer,
        None,
        new_name,
        'image/jpeg',
        buffer.getbuffer().nbytes,
        None
    )

    return compressed_file, new_name