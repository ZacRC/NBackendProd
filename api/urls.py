from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('test/', views.test_api, name='test_api'),
    path('upload_video/', views.upload_video),
    path('test/', views.test_api),
    path('user_info/', views.get_user_info),
    path('change_email/', views.change_email),
    path('change_password/', views.change_password),
    path('admin/dashboard/', views.admin_dashboard),
    path('admin/<str:model_name>/update/<int:pk>/', views.update_item),
    path('admin/<str:model_name>/delete/<int:pk>/', views.delete_item),
    path('track_activity/', views.track_user_activity),
    path('request-password-reset/', views.request_password_reset),
    path('reset-password/', views.reset_password),
    path('generate-code/', views.generate_code, name='generate_code'),
]