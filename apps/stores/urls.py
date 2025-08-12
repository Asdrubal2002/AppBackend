from django.urls import path
from . import views
from .views import (StoreListView, 
                    StoreMinimalListView, 
                    CategoryListView, 
                    StoreDetailView, 
                    create_category,
                    list_categories_by_store, 
                    create_review, 
                    StoreReviewList, 
                    StoreGeoListView, 
                    MyStoreView,
                    StoreStatsView,
                    UploadStoreMediaView,
                    StoreEditView,
                    update_category,
                    ShippingMethodsFromUserLocationAPIView,
                    StorePaymentMethodsAPIView,
                    search_products_and_stores,
                    ComboCreateView,
                    StoreComboListAPIView,
                    ComboDetailAPIView,
                    shipping_zones_view,
                    delete_shipping_zone,
                    shipping_methods_view,
                    delete_shipping_method,
                    shipping_method_zones_view,
                    delete_shipping_method_zone,
                    payment_methods_view,
                    create_coupon_view,
                    list_coupons_view,
                    coupon_detail_view,
                    create_bulk_subcategories,
                    ComboMediaUploadView,
                    ComboDeleteView,
                    add_store_admin, remove_store_admin,
                    list_store_admins,

                    )

urlpatterns = [
    # Calificar una tienda
    path('stores/<int:store_id>/review/', views.create_review, name='create-review'),

    # Obtener calificaciones de una tienda
    path('<int:store_id>/reviews/', StoreReviewList.as_view(), name='store-reviews'),
    
    path('create/', views.create_store, name='create_store'),
    path('my-store/', MyStoreView.as_view(), name='my-store'),
    path('stats/', StoreStatsView.as_view(), name='store-stats'),
    path('<slug:slug>/upload-media/', UploadStoreMediaView.as_view(), name='upload-store-media'),
    path('<int:pk>/edit/', StoreEditView.as_view(), name='store-edit'),
    
    path('stores/', StoreListView.as_view(), name='store-list'),
    path('minimal/', StoreMinimalListView.as_view(), name='store-minimal-list'),
    
    path('stores/geo/', StoreGeoListView.as_view(), name='store-list-geo'),
    
    path('categories/', CategoryListView.as_view(), name='store-categories'),
    path('store/<slug:slug>/', StoreDetailView.as_view(), name='store-detail'),
    path('<int:store_id>/categories/', list_categories_by_store, name='list-categories-by-store'),
        
    path('categories/create/', create_category, name='create-category'),

    path('categories/creates/', create_bulk_subcategories, name='creates-same-category'),

    path('categories/edit/<int:category_id>/', views.update_category, name='update-category'),
     # Eliminar categoría (DELETE)
    path('categories/delete/<int:category_id>/', views.delete_category, name='delete-category'),

    #Crear la rewiew sobre la STORE.
    path('create/<int:store_id>/review/', create_review, name='create-review'),
    
    path('user-location/', ShippingMethodsFromUserLocationAPIView.as_view(), name='localizar-shippings-user'),
    path('payment-methods/', StorePaymentMethodsAPIView.as_view(), name='payment-methods'),
    
    path('search/', search_products_and_stores, name='payment-methods'),

    path('create-combo/', ComboCreateView.as_view(), name='combo-create'),


    path('combos/<int:combo_id>/upload-media/', ComboMediaUploadView.as_view(), name='combo-create-media'),

    path('combos/<int:pk>/delete/', ComboDeleteView.as_view(), name='combo-delete'),

    path('stores/<int:store_id>/combos/', StoreComboListAPIView.as_view(), name='store-combos'),

    path('combo/<int:id>/', ComboDetailAPIView.as_view(), name='combo-detail'),

    path('shipping-zones/', shipping_zones_view, name='shipping-zones'),
    path('shipping-zones/<int:pk>/', delete_shipping_zone, name='delete-shipping-zone'),
    path('shipping-methods/', shipping_methods_view, name='shipping-methods'),
    path('shipping-methods/<int:pk>/', delete_shipping_method, name='delete-shipping-methods'),

    path('shipping-method-zones/', shipping_method_zones_view),
    path('shipping-method-zones/<int:pk>/', delete_shipping_method_zone),

    path('payment-methods-admin/', payment_methods_view, name='payment-methods'),

    path('create-coupon/', create_coupon_view, name='create-coupon'),

    path('coupons/', list_coupons_view, name='list-coupons'),
    path('coupons/<int:pk>/', coupon_detail_view, name='coupon-detail'),

    path('<int:store_id>/add-admin/', add_store_admin, name='add_store_admin'),
    path('<int:store_id>/admins/', list_store_admins, name='list_store_admins'),
    path('<int:store_id>/remove-admin/', remove_store_admin, name='remove_store_admin'),
    ]

