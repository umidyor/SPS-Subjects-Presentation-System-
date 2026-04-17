"""
SPS API Views
REST API ViewSets with proper permissions and filtering
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg, Q, Sum
from django.db import transaction,models
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
import openpyxl

from .models import (
    Subject, Topic, Resource, Quiz, Question,
    Choice, QuizAttempt, StudentResponse
)
from .serializers import (
    SubjectSerializer, TopicSerializer, ResourceSerializer,
    QuizSerializer, QuizPublicSerializer, QuestionSerializer,
    QuizAttemptSerializer, QuizSubmissionSerializer,
    LeaderboardEntrySerializer, QuizStatsSerializer
)
from .permissions import IsTeacher, IsOwner
from .pagination import StandardResultsSetPagination


class SubjectViewSet(viewsets.ModelViewSet):
    """Subject CRUD operations"""
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['subject_name', 'description']
    ordering_fields = ['created_at', 'subject_name']
    ordering = ['-created_at']
    lookup_field = 'subject_uuid'    
    def get_queryset(self):
        return Subject.objects.filter(
            teacher=self.request.user
        ).annotate(
            topics_count=Count('topics'),
            quizzes_count=Count('topics__quizzes')
        )
    
    def perform_create(self, serializer):
        serializer.save(teacher=self.request.user)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get detailed statistics for a subject"""
        subject = self.get_object()
        topics = Topic.objects.filter(subject=subject, teacher=request.user)
        quizzes = Quiz.objects.filter(topic__in=topics)
        
        total_attempts = QuizAttempt.objects.filter(
            quiz__in=quizzes, is_completed=True
        ).count()
        
        passed_count = sum(
            1 for a in QuizAttempt.objects.filter(quiz__in=quizzes, is_completed=True)
            if a.percentage >= 70
        )
        
        return Response({
            'topics_count': topics.count(),
            'quizzes_count': quizzes.count(),
            'total_attempts': total_attempts,
            'passed_count': passed_count,
            'failed_count': total_attempts - passed_count
        })


class TopicViewSet(viewsets.ModelViewSet):
    """Topic CRUD operations"""
    serializer_class = TopicSerializer
    permission_classes = [IsAuthenticated, IsTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['topic_name', 'description']
    ordering_fields = ['order', 'created_at']
    ordering = ['order', 'created_at']
    lookup_field = 'topic_uuid'
    
    def get_queryset(self):
        queryset = Topic.objects.filter(
            teacher=self.request.user
        ).select_related('subject').annotate(
            resources_count=Count('resources'),
            quizzes_count=Count('quizzes')
        )
        
        subject_uuid = self.request.query_params.get('subject_uuid')
        if subject_uuid:
            queryset = queryset.filter(subject__subject_uuid=subject_uuid)
        
        return queryset
    
    def perform_create(self, serializer):
        subject = serializer.validated_data['subject']
        if subject.teacher != self.request.user:
            raise PermissionError("You can only create topics in your own subjects")
        
        # Get last order
        last_order = Topic.objects.filter(subject=subject).aggregate(
            max_order=models.Max('order')
        )['max_order'] or 0
        
        serializer.save(teacher=self.request.user, order=last_order + 1)
    
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reorder topics"""
        orders = request.data.get('orders', [])
        
        with transaction.atomic():
            for item in orders:
                Topic.objects.filter(
                    id=item['id'],
                    teacher=request.user
                ).update(order=item['order'])
        
        return Response({'status': 'success'})


class ResourceViewSet(viewsets.ModelViewSet):
    """Resource CRUD operations"""
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated, IsTeacher]
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['order', 'created_at']
    ordering = ['order', 'created_at']
    lookup_field = 'resource_uuid'
    
    def get_queryset(self):
        queryset = Resource.objects.filter(teacher=self.request.user)
        
        topic_uuid = self.request.query_params.get('topic_uuid')
        if topic_uuid:
            queryset = queryset.filter(topic__topic_uuid=topic_uuid)
        
        return queryset
    
    def perform_create(self, serializer):
        print(serializer)
        topic = serializer.validated_data['topic']
        if topic.teacher != self.request.user:
            raise PermissionError("You can only add resources to your own topics")
        
        # Get last order
        last_order = Resource.objects.filter(topic=topic).aggregate(
            max_order=models.Max('order')
        )['max_order'] or 0
        
        # Detect file type
        file = serializer.validated_data['file']
        filename = file.name.lower()
        
        if filename.endswith('.pdf'):
            file_type = 'pdf'
        elif filename.endswith(('.ppt', '.pptx')):
            file_type = 'pptx'
        elif filename.endswith(('.doc', '.docx')):
            file_type = 'docx'
        else:
            file_type = 'other'
        
        serializer.save(
            teacher=self.request.user,
            order=last_order + 1,
            file_type=file_type,
            file_size=file.size
        )
    
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reorder resources"""
        orders = request.data.get('orders', [])
        
        with transaction.atomic():
            for item in orders:
                Resource.objects.filter(
                    id=item['id'],
                    teacher=request.user
                ).update(order=item['order'])
        
        return Response({'status': 'success'})


class QuizViewSet(viewsets.ModelViewSet):
    """Quiz CRUD operations (Teacher)"""
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated, IsTeacher]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'title']
    ordering = ['-created_at']
    lookup_field = 'quiz_uuid'
    
    def get_queryset(self):
        user_topics = Topic.objects.filter(teacher=self.request.user)
        queryset = Quiz.objects.filter(
            topic__in=user_topics
        ).select_related('topic', 'topic__subject').annotate(
            attempt_count=Count('attempts', filter=Q(attempts__is_completed=True)),
            avg_score=Avg('attempts__score', filter=Q(attempts__is_completed=True))
        )
        
        topic_uuid = self.request.query_params.get('topic_uuid')
        if topic_uuid:
            queryset = queryset.filter(topic__topic_uuid=topic_uuid)
        
        return queryset
    
    def perform_create(self, serializer):
        topic = serializer.validated_data['topic']
        if topic.teacher != self.request.user:
            raise PermissionError("You can only create quizzes in your own topics")
        
        serializer.save(teacher=self.request.user)
    
    @action(detail=True, methods=['post'])
    def regenerate_code(self, request, quiz_uuid=None):
        """Regenerate session code"""
        quiz = self.get_object()
        quiz.end_session()
        new_code = quiz.generate_session_code()
        return Response({'session_code': new_code})
    
    @action(detail=True, methods=['post'])
    def end_session(self, request, quiz_uuid=None):
        """End quiz session"""
        quiz = self.get_object()
        quiz.end_session()
        return Response({'status': 'Session ended'})
    
    @action(detail=True, methods=['get'])
    def results(self, request, quiz_uuid=None):
        """Get quiz results and statistics"""
        quiz = self.get_object()
        attempts = QuizAttempt.objects.filter(
            quiz=quiz, is_completed=True
        ).order_by('-score', 'completed_at')
        
        max_score = sum(q.points for q in quiz.questions.all())
        total_students = attempts.count()
        passed_count = sum(1 for a in attempts if a.percentage >= 70)
        avg_score = attempts.aggregate(avg=Avg('score'))['avg'] or 0
        
        stats = QuizStatsSerializer({
            'total_attempts': total_students,
            'average_score': round(avg_score, 1),
            'passed_count': passed_count,
            'failed_count': total_students - passed_count,
            'max_possible_score': max_score
        })
        
        serializer = QuizAttemptSerializer(attempts, many=True)
        
        return Response({
            'quiz': QuizSerializer(quiz).data,
            'stats': stats.data,
            'attempts': serializer.data
        })
    
    @action(detail=True, methods=['get'])
    def export_excel(self, request, quiz_uuid=None):
        """Export quiz results to Excel"""
        quiz = self.get_object()
        attempts = QuizAttempt.objects.filter(
            quiz=quiz, is_completed=True
        ).order_by('-score')
        
        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Results"
        
        # Headers
        headers = ["#", "Student Name", "Score", "Max Score", "Percentage", "Status", "Completed At"]
        ws.append(headers)
        
        # Data
        for idx, attempt in enumerate(attempts, 1):
            pct = attempt.percentage
            status_text = "Passed ✓" if pct >= 70 else "Failed ✗"
            ws.append([
                idx,
                attempt.student_name,
                attempt.score,
                attempt.max_score,
                f"{pct}%",
                status_text,
                attempt.completed_at.strftime("%Y-%m-%d %H:%M") if attempt.completed_at else ""
            ])
        
        # Save to response
        from django.http import HttpResponse
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{quiz.title}_results.xlsx"'
        wb.save(response)
        return response


# Public Quiz Views (No Authentication Required)

@api_view(['GET'])
@permission_classes([AllowAny])
def quiz_public_detail(request, quiz_uuid):
    """Get quiz details for students (public)"""
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid, is_active=True)
    
    if quiz.session_ended:
        return Response(
            {'error': 'Quiz session has ended'},
            status=status.HTTP_410_GONE
        )
    
    serializer = QuizPublicSerializer(quiz, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def quiz_submit(request, quiz_uuid):
    """Submit quiz answers (public)"""
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid, is_active=True)
    
    if quiz.session_ended:
        return Response(
            {'error': 'Quiz session has ended'},
            status=status.HTTP_410_GONE
        )
    
    serializer = QuizSubmissionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    student_name = serializer.validated_data['student_name']
    answers = serializer.validated_data['answers']
    
    with transaction.atomic():
        # Create attempt
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_name=student_name,
            started_at=timezone.now()
        )
        
        # Process answers
        questions = quiz.questions.prefetch_related('choices').all()
        max_score = sum(q.points for q in questions)
        total_score = 0.0
        
        for question in questions:
            # Get student's selected choice IDs for this question
            answer_data = next(
                (a for a in answers if a.get('question_id') == question.id),
                None
            )
            selected_ids = answer_data.get('choice_ids', []) if answer_data else []
            
            # Validate selected choices
            valid_choices = list(
                question.choices.filter(id__in=selected_ids).values_list('id', flat=True)
            )
            
            # Check if correct
            correct_ids = sorted(
                question.choices.filter(is_correct=True).values_list('id', flat=True)
            )
            is_correct = sorted(valid_choices) == correct_ids and len(correct_ids) > 0
            earned = question.points if is_correct else 0
            
            # Save response
            response = StudentResponse.objects.create(
                attempt=attempt,
                question=question,
                is_correct=is_correct,
                earned_points=earned
            )
            if valid_choices:
                response.selected_choices.set(valid_choices)
            
            total_score += earned
        
        # Update attempt
        attempt.score = total_score
        attempt.max_score = max_score
        attempt.is_completed = True
        attempt.completed_at = timezone.now()
        attempt.save()
    
    # Return result
    serializer = QuizAttemptSerializer(attempt)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def quiz_result(request, attempt_uuid):
    """Get quiz attempt result (public)"""
    attempt = get_object_or_404(
        QuizAttempt,
        attempt_uuid=attempt_uuid,
        is_completed=True
    )
    
    serializer = QuizAttemptSerializer(attempt)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def quiz_leaderboard(request, quiz_uuid):
    """Get live leaderboard (public)"""
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)
    
    attempts = QuizAttempt.objects.filter(
        quiz=quiz,
        is_completed=True
    ).order_by('-score', 'completed_at')[:30]
    
    leaderboard = []
    for idx, attempt in enumerate(attempts, 1):
        leaderboard.append({
            'rank': idx,
            'student_name': attempt.student_name,
            'score': attempt.score,
            'max_score': attempt.max_score,
            'percentage': attempt.percentage,
            'completed_at': attempt.completed_at
        })
    
    serializer = LeaderboardEntrySerializer(leaderboard, many=True)
    
    return Response({
        'total': attempts.count(),
        'session_ended': quiz.session_ended,
        'leaderboard': serializer.data
    })
