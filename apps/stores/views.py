from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import Store, Review, Category, CategoryProduct, PaymentMethod, Combo, Coupon
from .serializers import (ReviewSerializer, 
                          StoreSerializer, 
                          StoreMinimalSerializer, 
                          CategorySerializer, 
                          CategoryProductSerializer, 
                          CreateReviewSerializer, 
                          StoreGeoSerializer, 
                          StoreSerializerCreate, 
                          StoreAdminSerializer,
                          StoreStatsSerializer,
                          StoreUpdateSerializer,
                          PaymentMethodNameSerializer,
                          ComboCreateSerializer,
                          ComboSerializer,
                          ComboDetailSerializer,
                          ShippingZoneSerializer,
                          ShippingMethodSerializer,
                          ShippingMethodZoneSerializer,
                          PaymentMethodSerializer,
                          CouponSerializer,

                          )
from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import RetrieveAPIView
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework import status
from .filters import StoreFilter
from datetime import datetime
from django.utils import timezone
from math import radians, cos, sin, asin, sqrt
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.db.models import F
from rest_framework.generics import ListAPIView
from rest_framework import status, permissions, parsers
from ..utils import compress_image
from rest_framework.exceptions import PermissionDenied
# import spacy
# from transformers import pipeline
from collections import Counter
import random
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt  # Importa esto para desactivar CSRF
from pymongo import MongoClient
from django.conf import settings
from django.db import transaction
from .models import ShippingZone, ShippingMethodZone, ShippingMethod
from mongo_client.views.product.products import list_products
from mongo_client.models.product.products import process_products_with_images
from django.db.models import Q
from mongo_client.connection import mongo_db
from rest_framework.pagination import PageNumberPagination
from apps.users.models import User
from django.core.exceptions import ValidationError



products_collection = mongo_db["products"]

# Create your views here.
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_store(request):
    try:
        data = request.data.copy()

        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if latitude and longitude:
            try:
                location = Point(float(longitude), float(latitude))
                data['location'] = location
            except ValueError:
                return Response({'error': 'Latitud o longitud inválidas'}, status=400)

        serializer = StoreSerializerCreate(data=data)
        if serializer.is_valid():
            store = serializer.save()

            store.first_admin = request.user
            store.save()

            store.administrators.add(request.user)

            user = request.user
            if not user.is_seller:
                user.is_seller = True
                user.save()

            # ✅ Crear automáticamente una ShippingZone relacionada con la ubicación de la tienda
            try:
                ShippingZone.objects.create(
                    store=store,
                    country=store.country,
                    city=store.city,
                    neighborhood=store.neighborhood
                )
            except ValidationError as ve:
                print("Zona de envío ya existente:", ve)
                # Si quieres, puedes notificar esto en la respuesta
                # pero no es obligatorio si no es un error crítico

            return Response(StoreSerializerCreate(store).data, status=201)

        return Response(serializer.errors, status=400)

    except Exception as e:
        print("Error:", str(e))
        return Response({'error': str(e)}, status=400)



#Vista con filtros y búsqueda
class StoreListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = Store.objects.filter(is_active=True)
    serializer_class = StoreSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = StoreFilter
    search_fields = ['name', 'description', 'country__name', 'city__name', 'neighborhood__name']
    ordering_fields = ['average_rating', 'total_visits', 'created_at']
    ordering = ['-average_rating']  # orden por defecto
    
#Vista con filtros y búsqueda con menos recursos. 
class StoreMinimalListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = Store.objects.filter(is_active=True)
    serializer_class = StoreMinimalSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = StoreFilter
    search_fields = ['name', 'description', 'country__name', 'city__name', 'neighborhood__name']
    ordering_fields = ['average_rating', 'total_visits', 'created_at']
    ordering = ['-average_rating']

class StoreGeoListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = StoreGeoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = StoreFilter
    search_fields = ['name', 'description']
    ordering_fields = ['average_rating', 'total_visits', 'created_at']
    ordering = ['-average_rating']

    def get_queryset(self):
        lat = self.request.query_params.get('lat')
        lon = self.request.query_params.get('lon')
        base_qs = Store.objects.filter(is_active=True)

        if lat is not None and lon is not None:
            try:
                user_location = Point(float(lon), float(lat), srid=4326)
                base_qs = base_qs.filter(
                    location__distance_lte=(user_location, 1000)  # 3 km
                ).annotate(
                    distance=Distance('location', user_location)
                ).order_by('distance')
            except (TypeError, ValueError):
                pass  # Invalid lat/lon, ignora el filtro

        return base_qs
        
#Listar las categorias princiaples
class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None  # sin paginación
    queryset = Category.objects.all()

#Obtener una tienda especifica
class StoreDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    lookup_field = 'slug' 

    def get_object(self):
        store = get_object_or_404(Store, slug=self.kwargs['slug'])

        # Aumentar visitas (de forma atómica)
        Store.objects.filter(pk=store.pk).update(total_visits=F('total_visits') + 1)

        # Refrescar el objeto para mostrar el total actualizado
        store.refresh_from_db()

        return store



@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def shipping_zones_view(request):
    if request.method == 'GET':
        store_id = request.query_params.get('store')
        if store_id:
            try:
                store = Store.objects.get(id=store_id)
                if request.user not in store.administrators.all():
                    return Response({"detail": "No tienes permisos para ver zonas de esta tienda."}, status=status.HTTP_403_FORBIDDEN)
                zones = ShippingZone.objects.filter(store=store)
            except Store.DoesNotExist:
                return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Opcional: puedes decidir si permitir esto o no
            zones = ShippingZone.objects.filter(store__administrators=request.user)

        serializer = ShippingZoneSerializer(zones, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        store_id = request.data.get('store')
        if not store_id:
            return Response({"detail": "Falta el campo 'store'."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            store = Store.objects.get(id=store_id)
            if request.user not in store.administrators.all():
                return Response({"detail": "No tienes permisos para crear zonas para esta tienda."}, status=status.HTTP_403_FORBIDDEN)
        except Store.DoesNotExist:
            return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ShippingZoneSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_shipping_zone(request, pk):
    try:
        zone = ShippingZone.objects.get(pk=pk)
        if request.user not in zone.store.administrators.all():
            return Response(
                {"detail": "No tienes permisos para eliminar esta zona."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        zone.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)  # Sin cuerpo
    except ShippingZone.DoesNotExist:
        return Response(
            {"detail": "Zona no encontrada."}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def shipping_methods_view(request):
    if request.method == 'GET':
        store_id = request.query_params.get('store')
        if store_id:
            try:
                store = Store.objects.get(id=store_id)
                if request.user not in store.administrators.all():
                    return Response({"detail": "No tienes permisos para ver métodos de envío de esta tienda."}, status=status.HTTP_403_FORBIDDEN)
                methods = ShippingMethod.objects.filter(store=store)
            except Store.DoesNotExist:
                return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        else:
            methods = ShippingMethod.objects.filter(store__administrators=request.user)

        serializer = ShippingMethodSerializer(methods, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        store_id = request.data.get('store')
        if not store_id:
            return Response({"detail": "Falta el campo 'store'."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            store = Store.objects.get(id=store_id)
            if request.user not in store.administrators.all():
                return Response({"detail": "No tienes permisos para crear métodos de envío para esta tienda."}, status=status.HTTP_403_FORBIDDEN)
        except Store.DoesNotExist:
            return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ShippingMethodSerializer(data=request.data)
        if serializer.is_valid():
            method = serializer.save()

            # Buscar zonas de envío de la tienda
            zones = ShippingZone.objects.filter(store=store)

            # Si hay solo UNA zona, se asocia automáticamente
            if zones.count() == 1:
                ShippingMethodZone.objects.create(
                    shipping_method=method,
                    zone=zones.first()
                )

            return Response(ShippingMethodSerializer(method).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_shipping_method(request, pk):
    try:
        method = ShippingMethod.objects.get(pk=pk)
    except ShippingMethod.DoesNotExist:
        return Response({"detail": "Método de envío no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    # Validar que el usuario sea administrador de la tienda
    if request.user not in method.store.administrators.all():
        return Response({"detail": "No tienes permisos para eliminar este método de envío."}, status=status.HTTP_403_FORBIDDEN)

    method.delete()
    return Response({"detail": "Método de envío eliminado correctamente."}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def shipping_method_zones_view(request):
    if request.method == 'GET':
        store_id = request.query_params.get('store')
        if not store_id:
            return Response({"detail": "Falta el parámetro 'store'."}, status=status.HTTP_400_BAD_REQUEST)
        
        zones = ShippingMethodZone.objects.filter(shipping_method__store_id=store_id)
        serializer = ShippingMethodZoneSerializer(zones, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = ShippingMethodZoneSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_shipping_method_zone(request, pk):
    try:
        relation = ShippingMethodZone.objects.get(pk=pk)
    except ShippingMethodZone.DoesNotExist:
        return Response({"detail": "Relación no encontrada."}, status=status.HTTP_404_NOT_FOUND)

    relation.delete()
    return Response({"detail": "Relación eliminada correctamente."}, status=status.HTTP_200_OK)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def payment_methods_view(request):
    if request.method == 'GET':
        store_id = request.query_params.get('store')
        if not store_id:
            return Response({"detail": "Falta el parámetro 'store'."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            store = Store.objects.get(id=store_id)
            if request.user not in store.administrators.all():
                return Response({"detail": "No tienes permisos para ver los métodos de pago de esta tienda."}, status=status.HTTP_403_FORBIDDEN)
        except Store.DoesNotExist:
            return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        methods = PaymentMethod.objects.filter(store=store)
        serializer = PaymentMethodSerializer(methods, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        store_id = request.data.get('store')
        if not store_id:
            return Response({"detail": "Falta el campo 'store'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            store = Store.objects.get(id=store_id)
            if request.user not in store.administrators.all():
                return Response({"detail": "No tienes permisos para crear métodos de pago para esta tienda."}, status=status.HTTP_403_FORBIDDEN)
        except Store.DoesNotExist:
            return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PaymentMethodSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        method_id = request.query_params.get('id')
        if not method_id:
            return Response({"detail": "Falta el parámetro 'id'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            method = PaymentMethod.objects.get(id=method_id)
            if request.user not in method.store.administrators.all():
                return Response({"detail": "No tienes permisos para eliminar este método de pago."}, status=status.HTTP_403_FORBIDDEN)
            method.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PaymentMethod.DoesNotExist:
            return Response({"detail": "Método de pago no encontrado."}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_coupon_view(request):
    store_id = request.data.get('store')
    if not store_id:
        return Response({"detail": "Falta el campo 'store'."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

    if request.user not in store.administrators.all():
        return Response({"detail": "No tienes permisos para crear cupones en esta tienda."}, status=status.HTTP_403_FORBIDDEN)

    serializer = CouponSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(store=store)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def coupon_detail_view(request, pk):
    try:
        coupon = Coupon.objects.get(pk=pk)
    except Coupon.DoesNotExist:
        return Response({"detail": "Cupón no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    if request.user not in coupon.store.administrators.all():
        return Response({"detail": "No tienes permisos para acceder a este cupón."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        serializer = CouponSerializer(coupon)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = CouponSerializer(coupon, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        coupon.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_coupons_view(request):
    store_id = request.query_params.get('store')
    if not store_id:
        return Response({"detail": "Falta el parámetro 'store'."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        store = Store.objects.get(pk=store_id)
    except Store.DoesNotExist:
        return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

    if request.user not in store.administrators.all():
        return Response({"detail": "No tienes permisos para ver los cupones de esta tienda."}, status=status.HTTP_403_FORBIDDEN)

    coupons = Coupon.objects.filter(store=store)
    serializer = CouponSerializer(coupons, many=True)
    return Response(serializer.data)


class MyStoreView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        store = Store.objects.filter(administrators=request.user).first()
        if not store:
            return Response({'detail': 'No tienes una tienda registrada.'}, status=404)
        
        serializer = StoreAdminSerializer(store, context={'request': request})
        return Response(serializer.data)

class StoreStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        store = Store.objects.filter(administrators=request.user).first()
        if not store:
            return Response({"error": "No tienes tienda registrada."}, status=404)

        serializer = StoreStatsSerializer(store)
        return Response(serializer.data)

class UploadStoreMediaView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def patch(self, request, slug):
        store = get_object_or_404(Store, slug=slug)

        logo = request.FILES.get("logo")
        banner = request.FILES.get("banner")

        if logo:
            logo_compressed, _ = compress_image(logo)
            store.logo = logo_compressed
        if banner:
            banner_compressed, _ = compress_image(banner)
            store.banner = banner_compressed

        store.save()
        return Response({"detail": "Logo/Banner uploaded and compressed."}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_category(request):
    try:
        data = request.data.copy()
        store_id = data.get('store')
        name = data.get('name', '').strip()
        parent_id = data.get('parent')

        # Validar campos obligatorios
        if not store_id or not name:
            return Response({'error': 'Los campos "store" y "name" son obligatorios.'}, status=400)

        # Verificar tienda
        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({'error': 'La tienda no existe.'}, status=404)

        if request.user not in store.administrators.all():
            return Response({'error': 'No tienes permisos para crear categorías en esta tienda.'}, status=403)

        # Verificar categoría duplicada (mismo nivel)
        exists = CategoryProduct.objects.filter(
            store=store,
            parent_id=parent_id if parent_id else None,
            name__iexact=name  # Ignora mayúsculas/minúsculas
        ).exists()

        if exists:
            return Response({'error': 'Ya existe una categoría con ese nombre en este mismo nivel.'}, status=400)

        # Crear la categoría
        category = CategoryProduct(
            name=name,
            store=store,
            parent_id=parent_id if parent_id else None
        )
        category.save()

        return Response(CategoryProductSerializer(category).data, status=201)

    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bulk_subcategories(request):
    try:
        data = request.data
        store_id = data.get('store')
        parent_ids = data.get('parent_ids', [])
        name = data.get('name', '').strip()

        if not store_id or not name or parent_ids is None:
            return Response({'error': 'Debes enviar "store", "name" y "parent_ids".'}, status=400)

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({'error': 'La tienda no existe.'}, status=404)

        if request.user not in store.administrators.all():
            return Response({'error': 'No tienes permisos para crear categorías en esta tienda.'}, status=403)

        created = []
        skipped = []

        # Crear categoría principal si no hay parent_ids
        if not parent_ids:
            if CategoryProduct.objects.filter(
                store=store,
                parent__isnull=True,
                name__iexact=name
            ).exists():
                skipped.append({'parent_id': None, 'reason': 'Ya existe una categoría principal con ese nombre'})
            else:
                category = CategoryProduct.objects.create(
                    name=name,
                    store=store,
                    parent=None
                )
                created.append(CategoryProductSerializer(category).data)

        # Crear subcategorías
        for parent_id in parent_ids:
            if not CategoryProduct.objects.filter(id=parent_id, store=store).exists():
                skipped.append({'parent_id': parent_id, 'reason': 'Categoría padre no existe o no pertenece a la tienda'})
                continue

            if CategoryProduct.objects.filter(
                store=store,
                parent_id=parent_id,
                name__iexact=name
            ).exists():
                skipped.append({'parent_id': parent_id, 'reason': 'Ya existe una subcategoría con ese nombre'})
                continue

            category = CategoryProduct.objects.create(
                name=name,
                store=store,
                parent_id=parent_id
            )
            created.append(CategoryProductSerializer(category).data)

        return Response({'created': created, 'skipped': skipped}, status=201)

    except Exception as e:
        return Response({'error': str(e)}, status=400)




def is_descendant(parent, child):
    """
    Función auxiliar para verificar si una categoría es descendiente de otra
    """
    current = child.parent
    while current is not None:
        if current.id == parent.id:
            return True
        current = current.parent
    return False

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def update_category(request, category_id):
    try:
        # Obtener la categoría a editar
        category = CategoryProduct.objects.get(id=category_id)
        
        # Verificar permisos
        if request.user not in category.store.administrators.all():
            return Response({'error': 'No tienes permisos para editar esta categoría.'}, status=403)

        data = request.data.copy()
        
        # Validar si se intenta cambiar la tienda
        if 'store' in data and str(data['store']) != str(category.store.id):
            return Response({'error': 'No puedes cambiar la tienda de una categoría.'}, status=400)

        # Validación y procesamiento del campo 'parent'
        if 'parent' in data:
            new_parent_id = data['parent']
            
            # Validar que no sea padre de sí misma
            if str(new_parent_id) == str(category.id):
                return Response({'error': 'Una categoría no puede ser padre de sí misma.'}, status=400)
            
            # Validar existencia y misma tienda si se especifica un padre
            if new_parent_id:
                try:
                    new_parent = CategoryProduct.objects.get(id=new_parent_id)
                    if new_parent.store != category.store:
                        return Response({'error': 'La categoría padre debe pertenecer a la misma tienda.'}, status=400)
                    
                    # Validar jerarquía circular con nuestra función auxiliar
                    if is_descendant(category, new_parent):
                        return Response({'error': 'No puedes crear una jerarquía circular.'}, status=400)
                except CategoryProduct.DoesNotExist:
                    return Response({'error': 'La categoría padre especificada no existe.'}, status=400)
            
            # Asignar nuevo parent
            category.parent_id = new_parent_id if new_parent_id else None

        # Actualizar otros campos permitidos
        if 'name' in data:
            new_name = data['name'].strip()

            # Verificar si ya existe otra categoría con el mismo nombre en la misma tienda
            if CategoryProduct.objects.filter(
                store=category.store,
                name__iexact=new_name  # sin importar mayúsculas/minúsculas
            ).exclude(id=category.id).exists():
                return Response({'error': 'Ya existe otra categoría con ese nombre en esta tienda.'}, status=400)

            category.name = new_name

        category.save()
        return Response(CategoryProductSerializer(category).data, status=200)

    except CategoryProduct.DoesNotExist:
        return Response({'error': 'La categoría no existe.'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_category(request, category_id):
    try:
        # 1. Obtener la categoría de PostgreSQL
        category = CategoryProduct.objects.get(id=category_id)
        
        # 2. Verificar permisos
        if request.user not in category.store.administrators.all():
            return Response({'error': 'No tienes permisos para eliminar esta categoría.'}, status=403)

        # 3. Verificar subcategorías en PostgreSQL
        if category.subcategories.exists():
            return Response({
                'error': 'No se puede eliminar la categoría porque tiene subcategorías.',
                'subcategories_count': category.subcategories.count()
            }, status=400)

        # 4. Conectar a MongoDB y verificar productos
        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB_NAME]
        
        # Consulta para productos que usan esta categoría
        product_count = db.products.count_documents({
            'category_id': str(category.id) 
        })
        
        if product_count > 0:
            client.close()
            return Response({
                'error': 'No se puede eliminar la categoría porque tiene productos asociados.',
                'product_count': product_count
            }, status=400)

        # 5. Si todo está bien, proceder con la eliminación
        category.delete()
        
        # Opcional: Actualizar productos en MongoDB para quitar la referencia
        # db.products.update_many(
        #     {'category_id': str(category.id)},
        #     {'$set': {'category_id': None}}
        # )
        
        client.close()
        return Response({'success': 'Categoría eliminada correctamente.'}, status=200)

    except CategoryProduct.DoesNotExist:
        return Response({'error': 'La categoría no existe.'}, status=404)
    except Exception as e:
        return Response({'error': f'Error del servidor: {str(e)}'}, status=500)
    
@api_view(['GET'])
@permission_classes([AllowAny])
def list_categories_by_store(request, store_id):
    categories = CategoryProduct.objects.filter(store_id=store_id, parent__isnull=True)
    serializer = CategoryProductSerializer(categories, many=True)
    return Response(serializer.data)
    
#Vista para crear una review
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_review(request, store_id):
    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        return Response({'error': 'Tienda no encontrada'}, status=404)

    if Review.objects.filter(store=store, user=request.user).exists():
        return Response({'error': 'Ya calificaste esta tienda'}, status=400)

    serializer = CreateReviewSerializer(data=request.data)
    if serializer.is_valid():
        review = serializer.save(user=request.user, store=store)
        review.update_store_average_rating()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)

#Vista para listar reviews de una tienda
class StoreReviewList(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        store_id = self.kwargs['store_id']
        return Review.objects.filter(store_id=store_id).order_by('-created_at')
    
class StoreEditView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        store = get_object_or_404(Store, pk=pk)

        # Verificar permisos
        if request.user not in store.administrators.all():
            return Response(
                {"detail": "No tienes permiso para editar esta tienda."}, 
                status=403
            )

        serializer = StoreUpdateSerializer(
            instance=store, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        
        return Response(serializer.errors, status=400)
    
class ShippingMethodsFromUserLocationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if not user.neighborhood and not user.city and not user.country:
            return Response({"error": "User does not have location information."}, status=400)

        store_id = request.query_params.get('store_id')
        if not store_id:
            return Response({"error": "store_id is required as query parameter."}, status=400)

        def get_shipping_methods(zone_filter):
            zones = ShippingZone.objects.filter(store_id=store_id, **zone_filter)
            if not zones.exists():
                return []
            zone_ids = zones.values_list("id", flat=True)
            method_zones = ShippingMethodZone.objects.filter(
                zone_id__in=zone_ids,
                shipping_method__is_active=True
            ).select_related("shipping_method", "zone")

            result = []
            for mz in method_zones:
                method = mz.shipping_method
                result.append({
                    "id": method.id,
                    "description": method.description,
                    "zone_name": method.name,
                    "cost": mz.custom_cost if mz.custom_cost is not None else method.base_cost,
                    "days": mz.custom_days if mz.custom_days is not None else method.estimated_days,
                })
            return result

        # Prioridad: neighborhood → city → country
        methods = []
        if user.neighborhood:
            methods = get_shipping_methods({"neighborhood": user.neighborhood})
        if not methods and user.city:
            methods = get_shipping_methods({
                "city": user.city,
                "neighborhood__isnull": True
            })
        if not methods and user.country:
            methods = get_shipping_methods({
                "country": user.country,
                "city__isnull": True,
                "neighborhood__isnull": True
            })

        return Response({"shipping_methods": methods}, status=200)
    
class StorePaymentMethodsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        store_id = request.query_params.get('store_id')
        if not store_id:
            return Response({"error": "store_id is required."}, status=400)

        methods = PaymentMethod.objects.filter(store_id=store_id, is_active=True)
        serializer = PaymentMethodNameSerializer(methods, many=True)
        return Response({"payment_methods": serializer.data}, status=200)
    

class CustomPagination(PageNumberPagination):
    page_size = 10

@api_view(['GET'])
@permission_classes([AllowAny])
def search_products_and_stores(request):
    try:
        # Parámetros comunes
        product_page = int(request.GET.get("product_page", 1))
        store_page = int(request.GET.get("store_page", 1))
        page_size = int(request.GET.get("page_size", 10))
        lat = request.GET.get("lat")  # 👈 Mover aquí
        lon = request.GET.get("lon")  # 👈 Mover aquí

        # --------------------------
        # PRODUCTOS (NoSQL)
        # --------------------------
        product_filters = {
            "name": request.GET.get("name"),
            "description": request.GET.get("description"),
            "brand": request.GET.get("brand"),
            "category": request.GET.get("category"),
            "price_min": request.GET.get("price_min"),
            "price_max": request.GET.get("price_max"),
            "keywords": request.GET.get("keywords"),
            "search": request.GET.get("search"),
        }
        product_filters = {k: v for k, v in product_filters.items() if v}

        
        country_id = request.GET.get("country_id")
        city_id = request.GET.get("city_id")
        neighborhood_id = request.GET.get("neighborhood_id")

        products_data = list_products(
            country_id=country_id,
            city_id=city_id,
            neighborhood_id=neighborhood_id,
            page=product_page,
            page_size=page_size,
            filters=product_filters,
            lat=lat,
            lon=lon 
        )
        processed = process_products_with_images(products_data["results"], request)
        products_data["results"] = processed
        products_data["count"] = len(processed)


        # --------------------------
        # TIENDAS (SQL)
        # --------------------------
        store_search = request.GET.get("search", "")
        lat = request.GET.get("lat")
        lon = request.GET.get("lon")

        base_qs = Store.objects.filter(is_active=True)

        if city_id:
            base_qs = base_qs.filter(city_id=city_id)
        if neighborhood_id:
            base_qs = base_qs.filter(neighborhood_id=neighborhood_id)
        if country_id:
            base_qs = base_qs.filter(country_id=country_id)

        if store_search:
            base_qs = base_qs.filter(
                Q(name__icontains=store_search) |
                Q(description__icontains=store_search) |
                Q(country__name__icontains=store_search) |
                Q(city__name__icontains=store_search) |
                Q(neighborhood__name__icontains=store_search)
            )

        if lat and lon:
            try:
                user_location = Point(float(lon), float(lat), srid=4326)
                base_qs = base_qs.filter(
                    location__distance_lte=(user_location, 1000)
                ).annotate(
                    distance=Distance('location', user_location)
                ).order_by('distance')
            except (TypeError, ValueError):
                # Si hay error en lat/lon, aplicar orden por defecto
                base_qs = base_qs.order_by('id')
        else:
            base_qs = base_qs.order_by('id')  # aquí el orden por defecto

        # ✅ PAGINACIÓN CON REQUEST PERSONALIZADO PARA TIENDAS
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request

        factory = APIRequestFactory()
        store_fake_request = factory.get(
            '/fake-url',
            {
                'page': store_page,
                'page_size': page_size,
            }
        )
        store_fake_request = Request(store_fake_request)

        paginator = CustomPagination()
        store_paginated_qs = paginator.paginate_queryset(base_qs, store_fake_request)
        store_results = StoreMinimalSerializer(store_paginated_qs, many=True).data


        # --------------------------
        # RESPUESTA COMBINADA
        # --------------------------
        return Response({
            "products": products_data,
            "stores": {
                "results": store_results,
                "count": paginator.page.paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
            }
        }, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=400)

class ComboCreateView(generics.CreateAPIView):
    queryset = Combo.objects.all()
    serializer_class = ComboCreateSerializer
    permission_classes = [IsAuthenticated]


class ComboMediaUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, combo_id):
        try:
            combo = Combo.objects.get(id=combo_id, store__in=request.user.stores.all())
        except Combo.DoesNotExist:
            return Response({"error": "Combo no encontrado o no tienes acceso."}, status=404)

        image = request.FILES.get('image')  # 👈 usa el nombre correcto del campo

        if not image:
            return Response({"error": "Debes subir un archivo en el campo 'image'."}, status=400)

        combo.image = image  # 👈 asignar al campo correcto
        combo.save()
        combo.refresh_from_db()

        return Response({
            "message": "Imagen subida correctamente.",
            "image_url": combo.image.url  # 👈 accede al campo correcto
        }, status=200)


class ComboDeleteView(generics.DestroyAPIView):
    queryset = Combo.objects.all()
    serializer_class = ComboSerializer  # O usa uno más simple si solo necesitas mostrar el nombre
    permission_classes = [IsAuthenticated]


class StoreComboListAPIView(ListAPIView):
    serializer_class = ComboSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        store_id = self.kwargs.get("store_id")
        store = get_object_or_404(Store, id=store_id, is_active=True)
        return Combo.objects.filter(store=store, is_active=True).order_by('-created_at')

class ComboDetailAPIView(RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = Combo.objects.filter(is_active=True)
    serializer_class = ComboDetailSerializer
    lookup_field = 'id'  # o 'pk' si lo prefieres



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_store_admin(request, store_id):
    try:
        store = Store.objects.get(id=store_id)

        if store.first_admin != request.user:
            return Response({'error': 'Solo el primer administrador puede añadir otros administradores.'}, status=403)

        username = request.data.get('username')
        document_number = request.data.get('document_number')

        if not username or not document_number:
            return Response({'error': 'Se requiere username y número de documento.'}, status=400)

        try:
            user = User.objects.get(username=username, document_number=document_number)
        except User.DoesNotExist:
            return Response({'error': 'Usuario no encontrado con los datos proporcionados.'}, status=404)

        store.administrators.add(user)

        # Cambiar estado a vendedor si no lo es
        if not user.is_seller:
            user.is_seller = True
            user.save()

        return Response({'message': f'Usuario {user.username} añadido como administrador.'}, status=200)

    except Store.DoesNotExist:
        return Response({'error': 'Tienda no encontrada.'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_store_admins(request, store_id):
    try:
        store = Store.objects.get(id=store_id)

        if store.first_admin != request.user:
            return Response({'error': 'Solo el primer administrador puede ver esta información.'}, status=403)

        admins = store.administrators.all()

        data = [
            {
                'username': admin.username,
                'name': admin.name,
                'last_name': admin.last_name,
                'email': admin.email,
                'cellphone': admin.cellphone,
            }
            for admin in admins
        ]

        return Response({'administrators': data}, status=200)

    except Store.DoesNotExist:
        return Response({'error': 'Tienda no encontrada.'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_store_admin(request, store_id):
    try:
        store = Store.objects.get(id=store_id)

        # Solo el primer admin puede eliminar
        if store.first_admin != request.user:
            return Response({'error': 'Solo el primer administrador puede eliminar administradores.'}, status=403)

        username = request.data.get('username')

        if not username:
            return Response({'error': 'Se requiere el username del administrador a eliminar.'}, status=400)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'Usuario no encontrado.'}, status=404)

        if user == store.first_admin:
            return Response({'error': 'No se puede eliminar al primer administrador.'}, status=403)

        if user not in store.administrators.all():
            return Response({'error': 'El usuario no es administrador de esta tienda.'}, status=400)

        store.administrators.remove(user)
        return Response({'message': f'Usuario {user.username} eliminado como administrador.'}, status=200)

    except Store.DoesNotExist:
        return Response({'error': 'Tienda no encontrada.'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)
