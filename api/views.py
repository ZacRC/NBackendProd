from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from .serializers import RegisterSerializer, LoginSerializer, VideoSerializer, UserSerializer, UserActivitySerializer, AdminDashboardAnalyticsSerializer
from .models import Video, UserActivity
import os
import whisper
import logging
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .models import Video
from .serializers import UserSerializer, VideoSerializer
from django.apps import apps
from django.contrib.auth.models import User
from django.apps import apps
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from .models import UserActivity
from .serializers import UserActivitySerializer, AdminDashboardAnalyticsSerializer

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    logger.debug(f"Register request data: {request.data}")
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        logger.debug(f"Register response data: {serializer.data}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    logger.debug(f"Register errors: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])  # Add this line
def login(request):
    logger.debug(f"Login request data: {request.data}")
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        response_data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        logger.debug(f"Login response data: {response_data}")
        return Response(response_data)
    logger.debug(f"Login errors: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    logger.debug(f"Logout request data: {request.data}")
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            logger.debug("Refresh token not provided")
            return Response({"error": "Refresh token not provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        token = RefreshToken(refresh_token)
        token.blacklist()
        logger.debug("Logout successful")
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
    except TokenError as e:
        logger.debug(f"Logout error: {e}")
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.debug(f"Logout error: {e}")
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_video(request):
    logger.debug(f"Upload video request data: {request.data}")
    serializer = VideoSerializer(data=request.data)
    if serializer.is_valid():
        video = serializer.save(user=request.user)
        transcription = transcribe_video(video.video_file.path)
        video.transcription = transcription
        video.save()
        response_data = VideoSerializer(video).data
        logger.debug(f"Upload video response data: {response_data}")
        return Response(response_data, status=status.HTTP_201_CREATED)
    logger.debug(f"Upload video errors: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def transcribe_video(video_path):
    model = whisper.load_model("base")
    result = model.transcribe(video_path)
    os.remove(video_path)  # Clean up the uploaded file
    return result['text']

@api_view(['GET'])
@permission_classes([AllowAny])
def test_api(request):
    logger.debug("API test endpoint called")
    return Response({"message": "API confirmed"}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    user = request.user
    return Response({
        'username': user.username,
        'email': user.email,
        'date_joined': user.date_joined
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_email(request):
    user = request.user
    new_email = request.data.get('new_email')
    if new_email:
        user.email = new_email
        user.save()
        return Response({'message': 'Email updated successfully'})
    return Response({'error': 'New email is required'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    if current_password and new_password:
        if user.check_password(current_password):
            user.set_password(new_password)
            user.save()
            return Response({'message': 'Password updated successfully'})
        return Response({'error': 'Current password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'error': 'Current and new passwords are required'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dashboard(request):
    data = {}
    
    # Handle User model separately
    user_serializer = UserSerializer(User.objects.all(), many=True)
    data['user'] = user_serializer.data
    
    # Handle other models in the api app
    api_models = apps.get_app_config('api').get_models()
    for model in api_models:
        serializer_class = globals().get(f"{model.__name__}Serializer")
        if serializer_class:
            queryset = model.objects.all()
            serializer = serializer_class(queryset, many=True)
            data[model._meta.model_name] = serializer.data
    
    # Add user activity data
    user_activity = UserActivity.objects.all().order_by('-timestamp')[:100]  # Get last 100 activities
    user_activity_serializer = UserActivitySerializer(user_activity, many=True)
    data['user_activity'] = user_activity_serializer.data

    # Add analytics data
    seven_days_ago = timezone.now() - timedelta(days=7)
    analytics_data = {
        'total_users': User.objects.count(),
        'active_users_last_7_days': UserActivity.objects.filter(timestamp__gte=seven_days_ago).values('user').distinct().count(),
        'total_videos': Video.objects.count(),
        'videos_uploaded_last_7_days': Video.objects.filter(uploaded_at__gte=seven_days_ago).count(),
    }

    # Add page visit analytics
    page_visits = UserActivity.objects.filter(
        activity_type='page_visit',
        timestamp__gte=seven_days_ago
    ).values('details__page').annotate(count=Count('id')).order_by('-count')

    page_visit_data = [
        {'page': item['details__page'], 'visits': item['count']}
        for item in page_visits
    ]

    analytics_data['page_visits'] = page_visit_data

    analytics_serializer = AdminDashboardAnalyticsSerializer(analytics_data)
    data['analytics'] = analytics_serializer.data

    return Response(data)

@api_view(['PUT'])
@permission_classes([IsAdminUser])
def update_item(request, model_name, pk):
    if model_name.lower() == 'user':
        model = User
        serializer_class = UserSerializer
    else:
        model = apps.get_model(app_label='api', model_name=model_name)
        serializer_class = globals().get(f"{model.__name__}Serializer")
    
    if not serializer_class:
        return Response({"error": "Model not found"}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        item = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    serializer = serializer_class(item, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_item(request, model_name, pk):
    if model_name.lower() == 'user':
        model = User
    else:
        model = apps.get_model(app_label='api', model_name=model_name)
    
    try:
        item = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    item.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_user_activity(request):
    activity_type = request.data.get('activity_type')
    details = request.data.get('details', {})
    
    UserActivity.objects.create(
        user=request.user,
        activity_type=activity_type,
        details=details
    )
    
    return Response({"message": "Activity tracked successfully"}, status=status.HTTP_201_CREATED)