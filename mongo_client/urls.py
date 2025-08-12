from django.urls import path

from .views.product.products import (ProductListCreateView, 
                                    ProductDetailView, 
                                    list_products_by_store,
                                    list_all_products,
                                    DeleteStoreProductsView, 
                                    ProductMediaUploadView, 
                                    CleanProductMediaView, 
                                    DeleteProductView,
                                    ProductUpdateAPIView,
                                    DeleteProductImageView,
                                    )
from .views.post.posts import (PostCreateView,
                               StorePostListView, 
                               ToggleLikePostView, 
                               PostUpdateAPIView, 
                               PostDetailAPIView,
                               PostDeleteView,
                               LikedPostsView,
                               RecommendedPostsView,
                               PublicPostsView,
                               
                               
                               )
                               
from .views.post.media_upload import PostMediaUploadView, PostMediaDeleteView
from .views.comentsProcduct.comments import comment_create_view, comments_list_view
from .views.suggestion.suggestion import TipCreateView, RandomTipByCategoryView

urlpatterns = [
    path('create-product/', ProductListCreateView.as_view(), name='product-list-create'),
    path('product/<str:product_id>/', ProductDetailView.as_view(), name='product-detail'),
    path('store/<int:store_id>/', list_products_by_store, name='list-products-by-store'),
    path('all-products/', list_all_products, name='list-products'),

    path('media-upload/', ProductMediaUploadView.as_view(), name='product-media-upload'),
    path("products/<str:product_id>/", ProductUpdateAPIView.as_view(), name="product-update"),

    #Elimina todos los productos de una tienda en espcifico
    path("products/store/<int:store_id>/", DeleteStoreProductsView.as_view(), name="delete-store-products"),
    #Borra toda la media de un producto
    path("clean-media/", CleanProductMediaView.as_view(), name="clean-product-media"),
    #Borra una a una de la media
    path("delete-media-product/", DeleteProductImageView.as_view(), name="delete-product-media"),


    path("delete-product/", DeleteProductView.as_view(), name="delete-product-and-media"),


    #Posts
    path('create/post/', PostCreateView.as_view(), name='create-post'),
    path("posts/media-upload/", PostMediaUploadView.as_view(), name="post-media-upload"),
    path("store/<int:store_id>/posts/", StorePostListView.as_view(), name='post-list'),
    path("post/<str:post_id>/edit/", PostUpdateAPIView.as_view(), name='post-edit'),
    path("delete-media/post/", PostMediaDeleteView.as_view(), name='delete-media'),
    path("post/<post_id>/", PostDetailAPIView.as_view(), name='post-edit'),
    path('posts/delete/<str:post_id>/', PostDeleteView.as_view(), name='delete-post'),
    path('posts/recommended/', RecommendedPostsView.as_view(), name='post-recomendations'),
    path('posts/public/', PublicPostsView.as_view(), name='post-public'),

    path("posts/liked/", LikedPostsView.as_view(), name="liked-posts"),

    #Suggestion
    path("suggestion/tips/create/", TipCreateView.as_view(), name="tip-create"),
    path("suggestion/tips/<str:slug>/random/", RandomTipByCategoryView.as_view(), name="tip-random"),



    #Comments Products
    path('create/comment/', comment_create_view, name='create-comment'),
    path('comments/posts/<str:post_id>/', comments_list_view, name='comments'),
    path('toggle-like/<post_id>/', ToggleLikePostView.as_view(), name='lik-dislike'),



]