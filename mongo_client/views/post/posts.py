from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from ...models.post.serializers.serializersPosts import PostSerializer
from ...connection import mongo_db
from apps.stores.models import Store
from django.db.models import Q
from django.core.paginator import Paginator
from rest_framework.pagination import PageNumberPagination
import math
from bson import ObjectId
from ...models.post.post import process_post_with_absolute_media, get_post_by_id
from .recommendation import recommend_similar_posts
import random
posts_collection = mongo_db["post"]


PAGE_SIZE = 10 

class PostPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'

class PostCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        store_id = request.data.get('store_id')

        if not store_id:
            return Response({"error": "Se requiere el ID de la tienda"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({"error": "Tienda no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        # Verificar si el usuario es uno de los administradores de la tienda
        if not store.administrators.filter(id=user.id).exists():
            return Response({"error": "No tienes permiso para publicar en esta tienda"}, status=status.HTTP_403_FORBIDDEN)

        serializer = PostSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            post = serializer.save()
            return Response(PostSerializer(post, context={'request': request}).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StorePostListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, store_id):
        page = int(request.GET.get("page", 1))

        posts = list(
            posts_collection.find({"store_id": store_id}).sort("created_at", -1)
        )

        paginator = Paginator(posts, PAGE_SIZE)

        if page > paginator.num_pages:
            return Response({"error": "Página fuera de rango"}, status=404)

        current_page_posts = paginator.page(page).object_list
        
        for p in current_page_posts:
            p.setdefault("liked_by", [])
        
        # Procesar media con URL absoluta
        processed_posts = [process_post_with_absolute_media(p, request) for p in current_page_posts]

        serializer = PostSerializer(processed_posts, many=True, context={"request": request})

        return Response({
            "page": page,
            "total_pages": paginator.num_pages,
            "total_posts": paginator.count,
            "posts": serializer.data,
        })

class ToggleLikePostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        try:
            post = posts_collection.find_one({"_id": ObjectId(post_id)})
            if not post:
                return Response({"error": "Post no encontrado"}, status=404)

            user_id = request.user.id
            liked_by = post.get("liked_by", [])

            if user_id in liked_by:
                # Quitar like
                posts_collection.update_one(
                    {"_id": ObjectId(post_id)},
                    {
                        "$pull": {"liked_by": user_id},
                        "$inc": {"likes": -1}
                    }
                )
                updated_post = posts_collection.find_one({"_id": ObjectId(post_id)})
                return Response({
                    "is_liked": False,
                    "likes": updated_post.get("likes", 0)
                })
            else:
                # Agregar like
                posts_collection.update_one(
                    {"_id": ObjectId(post_id)},
                    {
                        "$addToSet": {"liked_by": user_id},
                        "$inc": {"likes": 1}
                    }
                )
                updated_post = posts_collection.find_one({"_id": ObjectId(post_id)})
                return Response({
                    "is_liked": True,
                    "likes": updated_post.get("likes", 0)
                })
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
class PostUpdateAPIView(APIView):
    def patch(self, request, post_id):
        post = get_post_by_id(post_id)
        if not post:
            return Response({"detail": "Post no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PostSerializer(instance=post, data=request.data, partial=True, context={"request": request})

        if serializer.is_valid():
            updated_post = serializer.save()
            return Response(PostSerializer(updated_post, context={"request": request}).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class PostDetailAPIView(APIView):
    def get(self, request, post_id):
        post = get_post_by_id(post_id)
        if not post:
            return Response({"detail": "Post no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PostSerializer(post, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class PostDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, post_id):
        post = get_post_by_id(post_id)
        if not post:
            return Response({"detail": "Publicación no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        store_id = post.get("store_id")
        if not store_id:
            return Response({"detail": "ID de tienda no encontrado en el post."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        # Verifica que el usuario sea administrador de la tienda
        if not store.administrators.filter(id=request.user.id).exists():
            return Response({"detail": "No autorizado para eliminar este post."}, status=status.HTTP_403_FORBIDDEN)

        result = posts_collection.delete_one({"_id": ObjectId(post_id)})

        if result.deleted_count == 1:
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({"detail": "Error al eliminar."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LikedPostsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = int(request.GET.get("page", 1))
        user_id = request.user.id

        # Buscar todos los posts donde este usuario ha dado like
        posts = list(
            posts_collection.find({
                "liked_by": {"$in": [user_id]}
            }).sort("created_at", -1)
        )

        paginator = Paginator(posts, PAGE_SIZE)

        if page > paginator.num_pages and paginator.num_pages > 0:
            return Response({"error": "Página fuera de rango"}, status=404)

        current_page_posts = paginator.page(page).object_list

        for p in current_page_posts:
            p.setdefault("liked_by", [])  # Por seguridad

        processed_posts = [process_post_with_absolute_media(p, request) for p in current_page_posts]

        serializer = PostSerializer(processed_posts, many=True, context={"request": request})

        return Response({
            "page": page,
            "total_pages": paginator.num_pages,
            "total_posts": paginator.count,
            "posts": serializer.data,
        })
    
class RecommendedPostsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", PAGE_SIZE))  # define PAGE_SIZE en tu config

        result = recommend_similar_posts(request.user, page, limit)
        processed = [process_post_with_absolute_media(p, request) for p in result["posts"]]
        serializer = PostSerializer(processed, many=True, context={"request": request})

        return Response({
            "page": result["page"],
            "total_pages": result["total_pages"],
            "total_posts": result["total_posts"],
            "posts": serializer.data,
        })
    
class PublicPostsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", PAGE_SIZE))

        # Puedes usar un filtro más sofisticado si lo deseas
        posts = list(
            posts_collection.find({})
            .sort("created_at", -1)
            .limit(100)
        )

        random.shuffle(posts)  # Para que no siempre vean los mismos

        paginator = Paginator(posts, limit)
        page = min(page, paginator.num_pages or 1)
        page_posts = paginator.page(page).object_list

        for p in page_posts:
            p.setdefault("liked_by", [])

        processed = [process_post_with_absolute_media(p, request) for p in page_posts]
        serializer = PostSerializer(processed, many=True, context={"request": request})

        return Response({
            "page": page,
            "total_pages": paginator.num_pages,
            "total_posts": paginator.count,
            "posts": serializer.data,
        })