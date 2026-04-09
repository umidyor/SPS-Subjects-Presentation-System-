import uuid
from django.contrib.auth.models import User
from django.db import models


class Subject(models.Model):
    subject_name = models.CharField(max_length=200)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#1a56db')  # hex color
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject_name


class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True)
    topic_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    topic_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.topic_name


class Resource(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to='resources/')
    pdf_file = models.FileField(upload_to="resources/pdf/", blank=True, null=True)
    file_type = models.CharField(max_length=200)
    order = models.IntegerField(default=0)  # NEW: for slide ordering
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title or self.file.name


class Quiz(models.Model):
    quiz_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    topic = models.ForeignKey('Topic', on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    time_limit = models.PositiveIntegerField(default=15, help_text="Minutlarda (quiz uchun umumiy)")
    is_active = models.BooleanField(default=True)
    # Kahoot-style: quiz session control
    session_code = models.CharField(max_length=8, blank=True, null=True, unique=True)
    session_started = models.BooleanField(default=False)
    session_ended = models.BooleanField(default=False)
    session_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def generate_session_code(self):
        import random, string
        while True:
            code = ''.join(random.choices(string.digits, k=6))
            if not Quiz.objects.filter(session_code=code, session_ended=False).exists():
                self.session_code = code
                self.session_ended = False
                self.session_started = False
                self.save()
                return code

    def end_session(self):
        """Expire the session so link no longer works"""
        self.session_ended = True
        self.session_started = False
        self.save()


class Question(models.Model):
    QUESTION_TYPES = (
        ('single', "Bitta to'g'ri javob (Radio)"),
        ('multiple', "Bir nechta to'g'ri javob (Checkbox)"),
        ('true_false', "To'g'ri / Noto'g'ri"),
    )

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    image = models.ImageField(upload_to='quiz_questions/', blank=True, null=True)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='single')
    points = models.PositiveIntegerField(default=5)
    order = models.PositiveIntegerField(default=0)
    # Kahoot-style: per-question time limit (seconds)
    time_limit_seconds = models.PositiveIntegerField(default=30, help_text="Sekundlarda (har bir savol)")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - {self.text[:40]}"


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    student_name = models.CharField(max_length=100)
    score = models.FloatField(default=0)
    max_score = models.FloatField(default=0)  # NEW: store max score at attempt time
    is_completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def percentage(self):
        if self.max_score > 0:
            return round((self.score / self.max_score) * 100)
        return 0

    def __str__(self):
        return f"{self.student_name} - {self.quiz.title} ({self.score}/{self.max_score})"


class StudentResponse(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(Choice, blank=True)
    is_correct = models.BooleanField(default=False)  # NEW: pre-computed
    earned_points = models.FloatField(default=0)      # NEW: pre-computed

    def __str__(self):
        return f"{self.attempt.student_name} - {self.question.text[:30]}"
