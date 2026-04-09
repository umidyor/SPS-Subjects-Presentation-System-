from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Subject / Topic
    path('subject/<str:subject_name>/', views.subjectdetails, name='subjectdetails'),
    path('topic/<uuid:topic_uuid>/', views.topicdetails, name='topicdetails'),

    # Resources
    path('topic/<uuid:topic_uuid>/upload/', views.ResourceUploadView.as_view(), name='resource_upload'),
    path('resource/<int:resource_id>/view/', views.resource_viewer, name='resource_viewer'),

    # Quiz — Teacher
    path('quiz/create/', views.create_quiz_view, name='create_quiz'),
    path('quiz/<uuid:quiz_uuid>/results/', views.quiz_results_admin, name='quiz_results_admin'),
    path('quiz/<uuid:quiz_uuid>/export/', views.export_results_excel, name='export_results_excel'),

    # Quiz — Student (no auth)
    path('quiz/<uuid:quiz_uuid>/take/', views.take_quiz_view, name='take_quiz'),
    path('quiz/attempt/<int:attempt_id>/result/', views.quiz_result_view, name='quiz_result'),
]
