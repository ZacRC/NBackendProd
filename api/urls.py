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
]