# views/post/media_upload.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny


from .files import save_post_file  # Este debes implementarlo o adaptar
#from ...models.products import compress_image  # Reutiliza el de productos si aplica
from ...utils.funcions import compress_image, safe_filename
from bson import ObjectId

from ...connection import mongo_db
posts_collection = mongo_db["post"]

class PostMediaUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        post_id = request.data.get("post_id")
        store_slug = request.data.get("store_slug").strip()

        files = request.FILES.getlist("files")
        
        print("FILES:", request.FILES)
        print("FILES.getlist('files'):", request.FILES.getlist("files"))
        for f in request.FILES.getlist("files"):
            print("Nombre:", f.name)
            print("Tipo:", f.content_type)


        if not post_id or not store_slug:
            return Response({"error": "post_id and store_slug are required"}, status=status.HTTP_400_BAD_REQUEST)

        media_objects = []

        for f in files:
            if f.content_type.startswith("image/"):
                compressed_file, name = compress_image(f)
                compressed_file.name = safe_filename(name)
                media_type = "image"
            elif f.content_type.startswith("video/"):
                compressed_file = f  # No compresión
                compressed_file.name = safe_filename(f.name)
                media_type = "video"
            else:
                continue

            media_info = save_post_file(request, store_slug, post_id, compressed_file)  # <-- corregido
            media_info["media_type"] = media_type
            media_objects.append(media_info)

        if media_objects:
            posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$push": {"media": {"$each": media_objects}}}
            )

        return Response({"media": media_objects}, status=status.HTTP_201_CREATED)


class PostMediaDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        post_id = request.query_params.get("post_id")
        media_url = request.query_params.get("media_url")

        if not post_id or not media_url:
            return Response({"error": "post_id and media_url are required"}, status=status.HTTP_400_BAD_REQUEST)

        result = posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$pull": {"media": {"url": media_url}}}
        )

        if result.modified_count == 0:
            return Response({"error": "Media not found or already removed"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"message": "Media removed successfully"}, status=status.HTTP_200_OK)
