"""
SPS API Serializers
Django REST Framework serializers with nested relationships
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from .models import (
    Subject, Topic, Resource, Quiz, Question, 
    Choice, QuizAttempt, StudentResponse
)


class UserSerializer(serializers.ModelSerializer):
    """User serializer for teacher info"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class SubjectSerializer(serializers.ModelSerializer):
    """Subject serializer with stats"""
    teacher = UserSerializer(read_only=True)
    topics_count = serializers.IntegerField(read_only=True)
    quizzes_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Subject
        fields = [
            'id', 'subject_uuid', 'subject_name', 'description', 
            'color', 'teacher', 'topics_count', 'quizzes_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'subject_uuid', 'created_at', 'updated_at']


class ResourceSerializer(serializers.ModelSerializer):
    """Resource serializer"""
    file = serializers.FileField(write_only=True)
    file_url = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()
    topic = serializers.SlugRelatedField(
        slug_field='topic_uuid', 
        queryset=Topic.objects.all(),
        required=True
    )    
    class Meta:
        model = Resource
        fields = [
            'id', 'resource_uuid', 'topic','title', 'file', 'file_url',
            'pdf_file', 'pdf_url', 'file_type', 'file_size',
            'order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'resource_uuid', 'created_at', 'updated_at']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
    
    def get_pdf_url(self, obj):
        request = self.context.get('request')
        if obj.pdf_file and request:
            return request.build_absolute_uri(obj.pdf_file.url)
        return None


class TopicSerializer(serializers.ModelSerializer):
    """Topic serializer with resources and quizzes"""
    resources = ResourceSerializer(many=True, read_only=True)
    resources_count = serializers.IntegerField(read_only=True)
    quizzes_count = serializers.IntegerField(read_only=True)
    subject_name = serializers.CharField(source='subject.subject_name', read_only=True)
    
    class Meta:
        model = Topic
        fields = [
            'id', 'topic_uuid', 'topic_name', 'description',
            'subject', 'subject_name', 'order', 'resources',
            'resources_count', 'quizzes_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'topic_uuid', 'created_at', 'updated_at']


class ChoiceSerializer(serializers.ModelSerializer):
    """Choice serializer"""
    class Meta:
        model = Choice
        fields = ['id', 'choice_uuid', 'text', 'is_correct', 'order']
        read_only_fields = ['id', 'choice_uuid']


class ChoicePublicSerializer(serializers.ModelSerializer):
    """Choice serializer without correct answers (for students)"""
    class Meta:
        model = Choice
        fields = ['id', 'choice_uuid', 'text', 'order']
        read_only_fields = ['id', 'choice_uuid']


class QuestionSerializer(serializers.ModelSerializer):
    """Question serializer with choices"""
    choices = ChoiceSerializer(many=True, required=False)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_uuid', 'text', 'image', 'image_url',
            'question_type', 'points', 'order', 'time_limit_seconds',
            'choices', 'created_at'
        ]
        read_only_fields = ['id', 'question_uuid', 'created_at']
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class QuestionPublicSerializer(serializers.ModelSerializer):
    """Question serializer for students (no correct answers)"""
    choices = ChoicePublicSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_uuid', 'text', 'image_url',
            'question_type', 'points', 'order', 'time_limit_seconds',
            'choices'
        ]
        read_only_fields = fields
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class QuizSerializer(serializers.ModelSerializer):
    """Quiz serializer with questions"""
    questions = QuestionSerializer(many=True, required=False)
    topic_name = serializers.CharField(source='topic.topic_name', read_only=True)
    subject_name = serializers.CharField(source='topic.subject.subject_name', read_only=True)
    attempt_count = serializers.IntegerField(read_only=True)
    avg_score = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'quiz_uuid', 'title', 'description', 'time_limit',
            'is_active', 'session_code', 'session_started', 'session_ended',
            'session_started_at', 'topic', 'topic_name', 'subject_name',
            'questions', 'attempt_count', 'avg_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'quiz_uuid', 'session_code', 'session_started',
            'session_ended', 'session_started_at', 'created_at', 'updated_at'
        ]
    
    @transaction.atomic
    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])
        quiz = Quiz.objects.create(**validated_data)
        quiz.generate_session_code()
        
        for q_data in questions_data:
            choices_data = q_data.pop('choices', [])
            question = Question.objects.create(quiz=quiz, **q_data)
            
            for c_data in choices_data:
                Choice.objects.create(question=question, **c_data)
        
        return quiz
    
    @transaction.atomic
    def update(self, instance, validated_data):
        questions_data = validated_data.pop('questions', None)
        
        # Update quiz fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update questions if provided
        if questions_data is not None:
            instance.questions.all().delete()
            
            for q_data in questions_data:
                choices_data = q_data.pop('choices', [])
                question = Question.objects.create(quiz=instance, **q_data)
                
                for c_data in choices_data:
                    Choice.objects.create(question=question, **c_data)
        
        return instance


class QuizPublicSerializer(serializers.ModelSerializer):
    """Quiz serializer for students"""
    questions = QuestionPublicSerializer(many=True, read_only=True)
    topic_name = serializers.CharField(source='topic.topic_name', read_only=True)
    subject_name = serializers.CharField(source='topic.subject.subject_name', read_only=True)
    
    class Meta:
        model = Quiz
        fields = [
            'quiz_uuid', 'title', 'description', 'time_limit',
            'topic_name', 'subject_name', 'questions', 'session_ended'
        ]
        read_only_fields = fields


class StudentResponseSerializer(serializers.ModelSerializer):
    """Student response serializer"""
    question_text = serializers.CharField(source='question.text', read_only=True)
    selected_choice_texts = serializers.SerializerMethodField()
    correct_choice_texts = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentResponse
        fields = [
            'id', 'question', 'question_text', 'selected_choices',
            'selected_choice_texts', 'correct_choice_texts',
            'is_correct', 'earned_points', 'answered_at'
        ]
        read_only_fields = fields
    
    def get_selected_choice_texts(self, obj):
        return [choice.text for choice in obj.selected_choices.all()]
    
    def get_correct_choice_texts(self, obj):
        return [choice.text for choice in obj.question.choices.filter(is_correct=True)]


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Quiz attempt serializer"""
    responses = StudentResponseSerializer(many=True, read_only=True)
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    percentage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'attempt_uuid', 'quiz', 'quiz_title', 'student_name',
            'score', 'max_score', 'percentage', 'is_completed',
            'started_at', 'completed_at', 'responses'
        ]
        read_only_fields = [
            'id', 'attempt_uuid', 'score', 'max_score', 'is_completed',
            'started_at', 'completed_at'
        ]


class AnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    choice_ids = serializers.ListField(child=serializers.IntegerField())


class QuizSubmissionSerializer(serializers.Serializer):
    """Serializer for quiz submission"""
    student_name = serializers.CharField(max_length=100)
    answers = AnswerSerializer(many=True)

    def validate_student_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Student name cannot be empty")
        return value.strip()

class LeaderboardEntrySerializer(serializers.Serializer):
    """Leaderboard entry serializer"""
    rank = serializers.IntegerField()
    student_name = serializers.CharField()
    score = serializers.FloatField()
    max_score = serializers.FloatField()
    percentage = serializers.IntegerField()
    completed_at = serializers.DateTimeField()


class QuizStatsSerializer(serializers.Serializer):
    """Quiz statistics serializer"""
    total_attempts = serializers.IntegerField()
    average_score = serializers.FloatField()
    passed_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    max_possible_score = serializers.IntegerField()
