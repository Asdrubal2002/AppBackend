from django.urls import path
from .views import (CartAPIView, 
                    UserCartListAPIView, 
                    UpdateCartItemQuantityAPIView, 
                    DeleteCartItemAPIView,
                    CheckoutAPIView,
                    CreateOrderAPIView,
                    UploadPaymentProofAPIView,
                    UserOrdersListAPIView,

                    StoreOrdersAdminView,
                    OrderAdminDetailView,
                    AddComboToCartAPIView,

                    UserCartDetailAPIView

                    )

urlpatterns = [
    path('cart/', CartAPIView.as_view(), name='cart-api'),
    path('user-carts/', UserCartListAPIView.as_view(), name='user-cart-list'),
    path('update-item-quantity/', UpdateCartItemQuantityAPIView.as_view(), name='update-cart-quantity'),
    path('delete-item/', DeleteCartItemAPIView.as_view(), name='deelte-product'),
    path("checkout/", CheckoutAPIView.as_view(), name="checkout"),
    
    path('orders/create/', CreateOrderAPIView.as_view()),
    path('orders/<int:order_id>/upload-proof/', UploadPaymentProofAPIView.as_view()),
    path('orders/my/', UserOrdersListAPIView.as_view()),

    path('orders/store/<int:store_id>/', StoreOrdersAdminView.as_view()),
    path('orders/<int:order_id>/', OrderAdminDetailView.as_view()),

    path("add-combo/", AddComboToCartAPIView.as_view()),

    path('user-carts/<int:pk>/', UserCartDetailAPIView.as_view(), name='user-cart-detail'),

]
