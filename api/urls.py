from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register),
    path('login/', views.login),
    path('logout/', views.logout),
    path('upload_video/', views.upload_video),
    path('test/', views.test_api),
    path('user_info/', views.get_user_info),
    path('change_email/', views.change_email),
    path('change_password/', views.change_password),
    path('admin/dashboard/', views.admin_dashboard),
    path('admin/<str:model_name>/update/<int:pk>/', views.update_item),
    path('admin/<str:model_name>/delete/<int:pk>/', views.delete_item),
    path('track_activity/', views.track_user_activity),
]