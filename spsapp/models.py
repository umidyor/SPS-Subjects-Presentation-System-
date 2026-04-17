"""
SPS API Models
Optimized for API-first architecture with proper indexing
"""
import uuid
from django.contrib.auth.models import User
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import random
import string


class Subject(models.Model):
    """Fan (Subject) - Math, Physics, etc."""
    id = models.BigAutoField(primary_key=True)
    subject_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subjects')
    subject_name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#1a56db')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', '-created_at']),
        ]

    def __str__(self):
        return self.subject_name


class Topic(models.Model):
    """Mavzu (Topic) - Chapter/Unit within a subject"""
    id = models.BigAutoField(primary_key=True)
    topic_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='topics')
    topic_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['subject', 'order']),
            models.Index(fields=['teacher', '-created_at']),
        ]

    def __str__(self):
        return f"{self.subject.subject_name} - {self.topic_name}"


class Resource(models.Model):
    """Resource - PPTX, PDF, DOCX files for presentations"""
    FILE_TYPES = (
        ('pdf', 'PDF'),
        ('pptx', 'PowerPoint'),
        ('docx', 'Word Document'),
        ('other', 'Other'),
    )
    
    id = models.BigAutoField(primary_key=True)
    resource_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='resources')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='resources/%Y/%m/')
    pdf_file = models.FileField(upload_to='resources/pdf/%Y/%m/', blank=True, null=True)
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='other')
    file_size = models.BigIntegerField(default=0)  # in bytes
    order = models.IntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['topic', 'order']),
        ]

    def __str__(self):
        return self.title


class Quiz(models.Model):
    """Quiz - Kahoot-style interactive quiz"""
    id = models.BigAutoField(primary_key=True)
    quiz_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='quizzes')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    time_limit = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(180)],
        help_text="Total quiz time in minutes"
    )
    is_active = models.BooleanField(default=True)
    
    # Session management
    session_code = models.CharField(max_length=8, blank=True, null=True, unique=True, db_index=True)
    session_started = models.BooleanField(default=False)
    session_ended = models.BooleanField(default=False)
    session_started_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['topic', '-created_at']),
            models.Index(fields=['teacher', '-created_at']),
            models.Index(fields=['session_code', 'session_ended']),
        ]

    def __str__(self):
        return self.title

    def generate_session_code(self):
        """Generate unique 6-digit session code"""
        while True:
            code = ''.join(random.choices(string.digits, k=6))
            if not Quiz.objects.filter(session_code=code, session_ended=False).exists():
                self.session_code = code
                self.session_ended = False
                self.session_started = False
                self.save(update_fields=['session_code', 'session_ended', 'session_started'])
                return code

    def end_session(self):
        """End quiz session"""
        self.session_ended = True
        self.session_started = False
        self.save(update_fields=['session_ended', 'session_started'])


class Question(models.Model):
    """Question within a quiz"""
    QUESTION_TYPES = (
        ('single', 'Single Choice'),
        ('multiple', 'Multiple Choice'),
        ('true_false', 'True/False'),
    )
    
    id = models.BigAutoField(primary_key=True)
    question_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    image = models.ImageField(upload_to='quiz_questions/%Y/%m/', blank=True, null=True)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='single')
    points = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    order = models.PositiveIntegerField(default=0, db_index=True)
    time_limit_seconds = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(300)],
        help_text="Time per question in seconds"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['quiz', 'order']),
        ]

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order + 1}"


class Choice(models.Model):
    """Answer choice for a question"""
    id = models.BigAutoField(primary_key=True)
    choice_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.question.text[:30]} - {self.text[:30]}"


class QuizAttempt(models.Model):
    """Student attempt at a quiz"""
    id = models.BigAutoField(primary_key=True)
    attempt_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student_name = models.CharField(max_length=100, db_index=True)
    score = models.FloatField(default=0)
    max_score = models.FloatField(default=0)
    is_completed = models.BooleanField(default=False, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-score', 'completed_at']
        indexes = [
            models.Index(fields=['quiz', 'is_completed', '-score']),
            models.Index(fields=['quiz', '-completed_at']),
        ]

    @property
    def percentage(self):
        if self.max_score > 0:
            return round((self.score / self.max_score) * 100)
        return 0

    def __str__(self):
        return f"{self.student_name} - {self.quiz.title} ({self.score}/{self.max_score})"


class StudentResponse(models.Model):
    """Student's answer to a question"""
    id = models.BigAutoField(primary_key=True)
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(Choice, blank=True)
    is_correct = models.BooleanField(default=False)
    earned_points = models.FloatField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['answered_at']

    def __str__(self):
        return f"{self.attempt.student_name} - {self.question.text[:30]}"
