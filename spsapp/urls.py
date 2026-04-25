"""
SPS API URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import (
    SubjectViewSet, TopicViewSet, ResourceViewSet, QuizViewSet, QuestionViewSet,
    quiz_public_detail, quiz_submit, quiz_result, quiz_leaderboard
)

# Router for ViewSets
router = DefaultRouter()
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'topics', TopicViewSet, basename='topic')
router.register(r'resources', ResourceViewSet, basename='resource')

urlpatterns = [
    # API Root
    path('', include(router.urls)),
    
    # Authentication
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
        path('quizzes/', QuizViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('quizzes/<uuid:quiz_uuid>/', QuizViewSet.as_view({
        'get': 'retrieve',
        'patch': 'update',
        'put': 'update',
        'delete': 'destroy'
    })),
    
    # Question endpoints (nested)
    path('quizzes/<uuid:quiz_uuid>/questions/', QuestionViewSet.as_view({
        'get': 'list',
        'post': 'create'
    })),
    path('quizzes/<uuid:quiz_uuid>/questions/<uuid:question_uuid>/', QuestionViewSet.as_view({
        'get': 'retrieve',
        'patch': 'update',
        'put': 'update',
        'delete': 'destroy'
    })),    

        path('quizzes/<uuid:quiz_uuid>/regenerate-code/', QuizViewSet.as_view({
        'post': 'regenerate_code'
    })),
    path('quizzes/<uuid:quiz_uuid>/end-session/', QuizViewSet.as_view({
        'post': 'end_session'
    })),
    path('quizzes/<uuid:quiz_uuid>/results/', QuizViewSet.as_view({
        'get': 'results'
    })),
    path('quizzes/<uuid:quiz_uuid>/export-excel/', QuizViewSet.as_view({
        'get': 'export_excel'
    })),
    # Public Quiz Endpoints (no auth)
    path('public/quiz/<uuid:quiz_uuid>/', quiz_public_detail, name='quiz_public_detail'),
    path('public/quiz/<uuid:quiz_uuid>/submit/', quiz_submit, name='quiz_submit'),
    path('public/quiz/result/<uuid:attempt_uuid>/', quiz_result, name='quiz_result'),
    path('public/quiz/<uuid:quiz_uuid>/leaderboard/', quiz_leaderboard, name='quiz_leaderboard'),
    
    # API Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
