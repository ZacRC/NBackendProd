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
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.db import transaction
from django.contrib.auth import get_user_model
from .utils import generate_reset_token, send_reset_email
from rest_framework.exceptions import NotFound
from django.apps import apps
from rest_framework_simplejwt.exceptions import TokenError
import anthropic

logger = logging.getLogger(__name__)

User = get_user_model()



@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    logger.info(f"Register request data: {request.data}")
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = serializer.save()
            logger.info(f"User registered successfully: {user.username}")
            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response({"error": f"Registration failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
    logger.error(f"Registration serializer errors: {serializer.errors}")
    return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    logger.debug(f"Login request data: {request.data}")
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        logger.info(f"User logged in successfully: {username}")
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    else:
        try:
            user = User.objects.get(username=username)
            logger.warning(f"Login attempt with incorrect password for user: {username}")
            return Response({'error': 'Incorrect password'}, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            logger.warning(f"Login attempt for non-existent user: {username}")
            return Response({'error': 'User does not exist'}, status=status.HTTP_401_UNAUTHORIZED)

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

    # Update page visit analytics to include anonymous visits
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
@permission_classes([AllowAny])
def track_user_activity(request):
    activity_type = request.data.get('activity_type')
    details = request.data.get('details')
    user = request.user if request.user and request.user.is_authenticated else None

    UserActivity.objects.create(
        user=user,
        activity_type=activity_type,
        details=details
    )

    return Response({"message": "Activity tracked successfully"}, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    email = request.data.get('email')
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        raise NotFound("No user found with this email address.")

    reset_token = generate_reset_token()
    profile, created = UserProfile.objects.get_or_create(user=user)
    profile.reset_token = reset_token
    profile.save()

    send_reset_email(email, reset_token)

    return Response({"message": "Password reset email sent."}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    token = request.data.get('token')
    new_password = request.data.get('new_password')

    try:
        profile = UserProfile.objects.get(reset_token=token)
        user = profile.user
    except UserProfile.DoesNotExist:
        raise NotFound("Invalid or expired reset token.")

    user.set_password(new_password)
    profile.reset_token = None
    user.save()
    profile.save()

    return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    # Your dashboard logic here
    return Response({"message": "Welcome to the dashboard"})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_code(request):
    prompt = request.data.get('prompt')
    if not prompt:
        return Response({"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = anthropic.Anthropic(
            api_key="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",
        )

        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=8192,
            temperature=0,
            system="You are an AI assistant specialized in generating ReactJS frontend designs based on user prompts. Your task is to generate and return only the code needed to implement the design, using Tailwind CSS for styling.\n\nGuidelines:\n\nCode-Only Output: Provide the complete ReactJS code required to implement the frontend design, including HTML, Tailwind CSS classes, and any necessary JavaScript. Do not include any explanations, comments, or non-code content in your response.\nAdvanced Styling: Use Tailwind CSS to go above and beyond with styling. Leverage Tailwind's utility classes to create polished, dynamic, and visually appealing user interfaces, including animations and transitions.\nComponent Structure: Organize the code into well-structured, reusable React components, ensuring that the design is modular and easy to maintain.\nResponsiveness: Ensure the design is fully responsive, utilizing Tailwind's responsive utilities to adapt seamlessly to different screen sizes and devices.\nAnimations: Incorporate smooth, visually appealing animations and transitions, using Tailwind CSS and additional libraries if necessary, to enhance the user experience.\nDark Mode: When applicable, use Tailwind's dark mode features, incorporating gradients and high contrast for a modern aesthetic.\nIntuitive Interpretation: Interpret user prompts creatively and accurately, delivering a design that meets or exceeds their expectations, even if the prompt is vague or abstract.\nYour output should consist solely of the ReactJS code using Tailwind CSS necessary to implement the requested design.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return Response({"generated_code": message.content[0].text})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)