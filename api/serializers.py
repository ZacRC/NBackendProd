from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Video, UserActivity  # Add UserActivity import here
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'password', 'email')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data['email']
        )
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if user and user.is_active:
            return {'user': user}
        raise serializers.ValidationError("Incorrect Credentials")

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ('id', 'user', 'video_file', 'transcription', 'uploaded_at')
        read_only_fields = ('id', 'user', 'transcription', 'uploaded_at')

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'is_staff', 'date_joined', 'password')
        extra_kwargs = {'password': {'write_only': True}}
        read_only_fields = ('id', 'date_joined')

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def update(self, instance, validated_data):
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        return super().update(instance, validated_data)

class UserActivitySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserActivity
        fields = ('id', 'username', 'activity_type', 'timestamp', 'details')

class AdminDashboardAnalyticsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    active_users_last_7_days = serializers.IntegerField()
    total_videos = serializers.IntegerField()
    videos_uploaded_last_7_days = serializers.IntegerField()
    page_visits = serializers.ListField(child=serializers.DictField())