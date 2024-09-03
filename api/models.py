from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Video(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video_file = models.FileField(upload_to='videos/')
    transcription = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    activity_type = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Anonymous'} - {self.activity_type} - {self.timestamp}"
