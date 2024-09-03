from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from .serializers import RegisterSerializer, LoginSerializer, VideoSerializer, UserSerializer
from .models import Video
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