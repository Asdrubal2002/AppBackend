from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.stores.models import Store
from .serializers import (UserRegistrationSerializer,
                          UsernameValidationSerializer, 
                          UserSerializer, 
                          MyTokenObtainPairSerializer,
                          UserEditSerializer)

from apps.stores.serializers import StoreMinimalSerializer, StoreGeoSerializer
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from .models import Device


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    user = request.user
    serializer = UserSerializer(user, context={'request': request})
    return Response(serializer.data)

class ValidateUsernameView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = UsernameValidationSerializer(data=request.data)
        if serializer.is_valid():
            return Response({"valid": True})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
       
class EditUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        serializer = UserEditSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Perfil actualizado correctamente.",
                "user": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FollowStoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, store_id):
        user = request.user
        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        if store in user.followed_stores.all():
            return Response({"detail": "Ya sigues esta tienda."}, status=status.HTTP_400_BAD_REQUEST)

        user.followed_stores.add(store)
        return Response({"detail": f"Ahora sigues la tienda {store.name}."}, status=status.HTTP_200_OK)

    def delete(self, request, store_id):
        user = request.user
        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({"detail": "Tienda no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        if store not in user.followed_stores.all():
            return Response({"detail": "No sigues esta tienda."}, status=status.HTTP_400_BAD_REQUEST)

        user.followed_stores.remove(store)
        return Response({"detail": f"Has dejado de seguir la tienda {store.name}."}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def is_following_store(request, store_id):
    user = request.user
    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        return Response({"detail": "Store not found"}, status=404)
    
    is_followed = store in user.followed_stores.all()
    return Response({"is_followed": is_followed})

class FollowedStoresView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StoreMinimalSerializer
    pagination_class = PageNumberPagination  # o tu clase personalizada

    def get_queryset(self):
        queryset = self.request.user.followed_stores.select_related('category')
        
        # Filtro por categoría
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Paginar normalmente
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
        else:
            serializer = self.get_serializer(queryset, many=True)

        # Categorías únicas (no importa paginación)
        all_categories = queryset.values('category__id', 'category__name', 'category__icon_name').distinct()
        clean_categories = [
            {'id': cat['category__id'], 'name': cat['category__name'], 'icon_name': cat['category__icon_name']}
            for cat in all_categories if cat['category__id'] is not None
        ]

        # Respuesta paginada con categorías
        if page is not None:
            paginated_response = self.get_paginated_response(serializer.data)
            paginated_response.data['categories'] = clean_categories
            return paginated_response

        # Sin paginación
        return Response({
            'stores': serializer.data,
            'categories': clean_categories
        })

        
class SaveFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('fcm_token')
        if not token:
            return Response({'error': 'Token requerido'}, status=400)

        Device.objects.update_or_create(
            user=request.user,
            defaults={'fcm_token': token}
        )
        return Response({'success': True})