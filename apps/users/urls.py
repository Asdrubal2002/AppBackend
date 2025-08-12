from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (UserRegistrationView, 
                    user_profile, 
                    LogoutView, 
                    ValidateUsernameView, 
                    FollowStoreView, 
                    is_following_store, 
                    CustomTokenObtainPairView,
                    EditUserProfileView,
                    FollowedStoresView,
                    SaveFCMTokenView
                    
                    
                    )

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('profile/', user_profile),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('validate-username/', ValidateUsernameView.as_view(), name='validate-username'),
    path('follow-store/<int:store_id>/', FollowStoreView.as_view(), name='follow-store'),
    path('is-following-store/<int:store_id>/', is_following_store, name='is_following_store'),
    path('user/edit/', EditUserProfileView.as_view(), name='edit-user-profile'),
    path('stores/followed/', FollowedStoresView.as_view(), name='followed-stores'),
    path('tokenFcm/', SaveFCMTokenView.as_view(), name='fcm'),

]