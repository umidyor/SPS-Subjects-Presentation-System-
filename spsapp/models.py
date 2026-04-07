import uuid

from django.contrib.auth.models import User
from django.db import models

class Subject(models.Model):
    subject_name = models.CharField(max_length=200)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.subject_name
class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True)
    topic_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    topic_name= models.CharField(max_length=200)
    order=models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.topic_name

class Resource(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    file=models.FileField(upload_to='resources/')
    file_type=models.CharField(max_length=200)
    created_at=models.DateTimeField(auto_now_add=True)


