from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from .serializers import RegisterSerializer, LoginSerializer, VideoSerializer
from .models import Video
import os
import whisper
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
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
def login(request):
    logger.debug(f"Login request data: {request.data}")
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password']
        )
        if user is not None:
            refresh = RefreshToken.for_user(user)
            response_data = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
            logger.debug(f"Login response data: {response_data}")
            return Response(response_data)
        logger.debug("Invalid credentials")
        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    logger.debug(f"Login errors: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def logout(request):
    logger.debug(f"Logout request data: {request.data}")
    try:
        refresh_token = request.data['refresh']
        token = RefreshToken(refresh_token)
        token.blacklist()
        logger.debug("Logout successful")
        return Response(status=status.HTTP_205_RESET_CONTENT)
    except Exception as e:
        logger.debug(f"Logout error: {e}")
        return Response(status=status.HTTP_400_BAD_REQUEST)

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
def test_api(request):
    logger.debug("API test endpoint called")
    return Response({"message": "API confirmed"}, status=status.HTTP_200_OK)