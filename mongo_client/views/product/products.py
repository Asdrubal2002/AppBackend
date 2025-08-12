from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from ...models.product.serializers.serializersProduct import ProductSerializer
from mongo_client.models.product.products import (create_product, 
                                                  list_products, get_product,
                                                  update_product, delete_product, 
                                                  delete_products_by_store, 
                                                  process_products_with_images, 
                                                  process_single_product_with_media
                                                  )
from rest_framework.decorators import api_view, permission_classes
from .files import save_product_file
from rest_framework.parsers import MultiPartParser
from ...connection import mongo_db
import os
from django.conf import settings
from ...utils.funcions import compress_image
from apps.stores.models import Store
from django.db.models import Q

products_collection = mongo_db["products"]

class ProductListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        store_id = request.query_params.get("store_id")
        filters = request.query_params.dict()
        result = list_products(store_id, filters=filters)
        result["results"] = process_products_with_images(result["results"], request)
        return Response(result)

    def post(self, request):
        data = request.data.copy()
        store_id = data.get("store_id")

        if not store_id:
            return Response({"error": "Se requiere store_id"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({"error": "Tienda no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if hasattr(store, 'administrators') and not store.administrators.filter(id=user.id).exists():
            return Response({"error": "No tienes permiso para crear productos en esta tienda."}, status=status.HTTP_403_FORBIDDEN)

        # Solo embebemos datos necesarios (sin nombres redundantes)
        data["store_name"] = store.name
        data["store_logo_url"] = store.logo.url if store.logo else ""
        data["store_slug"] = store.slug

        data["country_id"] = store.country.id if store.country else None
        data["city_id"] = store.city.id if store.city else None
        data["neighborhood_id"] = store.neighborhood.id if store.neighborhood else None

        serializer = ProductSerializer(data=data)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
      
class ProductUpdateAPIView(APIView):
    def put(self, request, product_id):
        # Obtener producto actual desde MongoDB
        product = get_product(product_id)
        if not product:
            return Response({"detail": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductSerializer(product, data=request.data)
        if serializer.is_valid():
            updated_product = serializer.save()
            return Response(updated_product, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProductMediaUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def post(self, request):
        store_slug = request.data.get("store_slug", "").strip()
        product_slug = request.data.get("product_slug", "").strip()
        files = request.FILES.getlist("files")

        media_objects = []
        errors = []

        for f in files:
            try:
                if f.content_type.startswith('image/'):
                    compressed_file, name = compress_image(f)
                    compressed_file.name = name
                    media_info = save_product_file(store_slug, product_slug, compressed_file)
                else:
                    media_info = save_product_file(store_slug, product_slug, f)

                media_objects.append(media_info)

            except Exception as e:
                errors.append({
                    "filename": f.name,
                    "error": str(e),
                    "type": f.content_type,
                })

        if media_objects:
            products_collection.update_one(
                {"slug": product_slug},
                {"$push": {"media": {"$each": media_objects}}}
            )

        response_data = {"files": media_objects}
        if errors:
            response_data["errors"] = errors

        return Response(
            response_data,
            status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED
        )

class ProductDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id):
        product = get_product(product_id)
        if product:
            # Paso 1: procesar imágenes u otros datos externos
            processed_product = process_single_product_with_media(product, request)

            # Paso 2: aplicar el serializer para incluir lógica como discounted_price
            serializer = ProductSerializer(processed_product)
            return Response(serializer.data)

        return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)


    def put(self, request, product_id):
        update_data = request.data
        updated = update_product(product_id, update_data)
        if updated:
            return Response({"message": "Product updated"})
        return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, product_id):
        deleted = delete_product(product_id)
        if deleted:
            return Response({"message": "Product deleted"})
        return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['GET'])
@permission_classes([AllowAny])
def list_products_by_store(request, store_id):
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))

        # Construir filtros desde los parámetros de la URL
        filters = {
            "name": request.GET.get("name"),
            "description": request.GET.get("description"),
            "brand": request.GET.get("brand"),
            "category": request.GET.get("category"),
            "price_min": request.GET.get("price_min"),
            "price_max": request.GET.get("price_max"),
            "keywords": request.GET.get("keywords"),
            "search": request.GET.get("search"), 
        }

        # Eliminar los filtros que son None
        filters = {k: v for k, v in filters.items() if v is not None}

        data = list_products(store_id=int(store_id), page=page, page_size=page_size, filters=filters)

        data["results"] = process_products_with_images(data["results"], request)

        return Response(data, status=200)
    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_all_products(request):
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))

        filters = {
            "name": request.GET.get("name"),
            "description": request.GET.get("description"),
            "brand": request.GET.get("brand"),
            "category": request.GET.get("category"),
            "price_min": request.GET.get("price_min"),
            "price_max": request.GET.get("price_max"),
            "keywords": request.GET.get("keywords"),
            "search": request.GET.get("search"),
            "store_category": request.GET.get("store_category"),
        }
        filters = {k: v for k, v in filters.items() if v not in (None, "", "null")}

        # Ubicación
        country_id = request.GET.get("country_id")
        city_id = request.GET.get("city_id")
        neighborhood_id = request.GET.get("neighborhood_id")

        lat = request.GET.get("lat")
        lon = request.GET.get("lon")
        lat = float(lat) if lat not in (None, "", "null") else None
        lon = float(lon) if lon not in (None, "", "null") else None

        data = list_products(
            country_id=country_id,
            city_id=city_id,
            neighborhood_id=neighborhood_id,
            page=page,
            page_size=page_size,
            filters=filters,
            lat=lat,
            lon=lon
        )

        data["results"] = process_products_with_images(data["results"], request)

        return Response(data, status=200)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=400)

class CleanProductMediaView(APIView):
    permission_classes = [AllowAny] # Ajusta según tu seguridad
    def post(self, request):
        product_slug = request.data.get("product_slug", "").strip()

        if not product_slug:
            return Response({"error": "El campo 'product_slug' es requerido."},
                            status=status.HTTP_400_BAD_REQUEST)

        product = products_collection.find_one({"slug": product_slug})
        if not product:
            return Response({"error": "Producto no encontrado."},
                            status=status.HTTP_404_NOT_FOUND)

        cleaned_media = []
        removed = []

        for media in product.get("media", []):
            relative_path = media["url"].replace(settings.MEDIA_URL, "")
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)

            if os.path.exists(file_path):
                cleaned_media.append(media)
            else:
                removed.append(media)

        if removed:
            products_collection.update_one(
                {"slug": product_slug},
                {"$set": {"media": cleaned_media}}
            )

        return Response({
            "removed_count": len(removed),
            "remaining_count": len(cleaned_media),
            "removed_items": removed
        }, status=status.HTTP_200_OK)


class DeleteProductImageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        product_slug = request.data.get("product_slug")
        image_url = request.data.get("image_url")

        if not product_slug or not image_url:
            return Response(
                {"error": "Se requieren 'product_slug' e 'image_url'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        product = products_collection.find_one({"slug": product_slug})
        if not product:
            return Response({"error": "Producto no encontrado."},
                            status=status.HTTP_404_NOT_FOUND)

        media = product.get("media", [])
        new_media = [m for m in media if not m["url"].strip().endswith(image_url.strip().split('/')[-1])]

        if len(new_media) == len(media):
            return Response({"error": "Imagen no encontrada en el producto."},
                            status=status.HTTP_404_NOT_FOUND)

        # Eliminar físicamente si existe
        relative_path = image_url.replace(settings.MEDIA_URL, "")
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        if os.path.exists(file_path):
            os.remove(file_path)

        # Actualizar en MongoDB
        products_collection.update_one(
            {"slug": product_slug},
            {"$set": {"media": new_media}}
        )

        return Response({
            "message": "Imagen eliminada correctamente.",
            "remaining_media": new_media
        }, status=status.HTTP_200_OK)



class DeleteProductView(APIView):
    permission_classes = [AllowAny]

    def delete(self, request):
        product_slug = request.data.get("product_slug", "").strip()

        product = products_collection.find_one({"slug": product_slug})
        if not product:
            return Response({"error": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        # Eliminar archivos asociados
        for media in product.get("media", []):
            relative_path = media["url"].replace(settings.MEDIA_URL, "")
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            if os.path.exists(file_path):
                os.remove(file_path)

        # Eliminar preview si tienes uno
        if "preview" in product:
            preview_path = product["preview"].replace(settings.MEDIA_URL, "")
            preview_file_path = os.path.join(settings.MEDIA_ROOT, preview_path)
            if os.path.exists(preview_file_path):
                os.remove(preview_file_path)

        # Eliminar el producto
        products_collection.delete_one({"slug": product_slug})

        return Response({"message": "Producto y archivos eliminados correctamente"}, status=status.HTTP_200_OK)

class DeleteStoreProductsView(APIView):
    permission_classes = [AllowAny]

    def delete(self, request, store_id):
        deleted_count = delete_products_by_store(store_id)
        return Response(
            {"deleted": deleted_count},
            status=status.HTTP_200_OK
        )