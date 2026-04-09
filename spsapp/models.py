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
    pdf_file = models.FileField(upload_to="resources/pdf/", blank=True, null=True)
    file_type=models.CharField(max_length=200)
    created_at=models.DateTimeField(auto_now_add=True)


class Quiz(models.Model):
    quiz_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    topic = models.ForeignKey('Topic', on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255, verbose_name="Test nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Yo'riqnoma")
    time_limit = models.PositiveIntegerField(default=15, help_text="Minutlarda")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    QUESTION_TYPES = (
        ('single', 'Bitta to\'g\'ri javobli (Radio)'),
        ('multiple', 'Bir nechta to\'g\'ri javobli (Checkbox)'),
        ('true_false', 'To\'g\'ri / Noto\'g\'ri'),
    )

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField(verbose_name="Savol matni")
    image = models.ImageField(upload_to='quiz_questions/', blank=True, null=True)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='single')
    points = models.PositiveIntegerField(default=5)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - {self.text[:30]}"

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255, verbose_name="Variant matni")
    is_correct = models.BooleanField(default=False, verbose_name="To'g'ri javobmi?")

    def __str__(self):
        return self.text

class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    student_name = models.CharField(max_length=100) 
    score = models.FloatField(default=0)
    is_completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student_name} - {self.quiz.title} ({self.score} ball)"

class StudentResponse(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(Choice) 
    def __str__(self):
        return f"{self.attempt.student_name} - {self.question.text[:20]}"
