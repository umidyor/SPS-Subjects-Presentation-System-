from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Subject CRUD
    path('subject/create/', views.subject_create, name='subject_create'),
    path('subject/<int:subject_id>/edit/', views.subject_edit, name='subject_edit'),
    path('subject/<int:subject_id>/delete/', views.subject_delete, name='subject_delete'),
    path('subject/<str:subject_name>/', views.subjectdetails, name='subjectdetails'),

    # Topic CRUD
    path('subject/<int:subject_id>/topic/create/', views.topic_create, name='topic_create'),
    path('topic/<uuid:topic_uuid>/', views.topicdetails, name='topicdetails'),
    path('topic/<uuid:topic_uuid>/edit/', views.topic_edit, name='topic_edit'),
    path('topic/<uuid:topic_uuid>/delete/', views.topic_delete, name='topic_delete'),
    path('topics/reorder/', views.topic_reorder, name='topic_reorder'),

    # Resources
    path('topic/<uuid:topic_uuid>/upload/', views.ResourceUploadView.as_view(), name='resource_upload'),
    path('resource/<int:resource_id>/view/', views.resource_viewer, name='resource_viewer'),
    path('resource/<int:resource_id>/delete/', views.resource_delete, name='resource_delete'),
    path('resources/reorder/', views.resource_reorder, name='resource_reorder'),

    # Quiz — Teacher
    path('quiz/', views.quiz_list, name='quiz_list'),
    path('quiz/create/', views.create_quiz_view, name='create_quiz'),
    path('quiz/<uuid:quiz_uuid>/edit/', views.quiz_edit, name='quiz_edit'),
    path('quiz/<uuid:quiz_uuid>/delete/', views.quiz_delete, name='quiz_delete'),
    path('quiz/<uuid:quiz_uuid>/results/', views.quiz_results_admin, name='quiz_results_admin'),
    path('quiz/<uuid:quiz_uuid>/export/', views.export_results_excel, name='export_results_excel'),
    path('quiz/<uuid:quiz_uuid>/live/', views.quiz_live_leaderboard, name='quiz_live_leaderboard'),
    path('quiz/<uuid:quiz_uuid>/leaderboard-data/', views.quiz_leaderboard_data, name='quiz_leaderboard_data'),
    path('quiz/<uuid:quiz_uuid>/regenerate-code/', views.quiz_regenerate_code, name='quiz_regenerate_code'),
    path('quiz/<uuid:quiz_uuid>/end-session/', views.quiz_end_session, name='quiz_end_session'),

    # Excel import
    path('quiz/excel/parse/', views.quiz_excel_parse, name='quiz_excel_parse'),

    # Quiz — Student (no auth)
    path('quiz/<uuid:quiz_uuid>/take/', views.take_quiz_view, name='take_quiz'),
    path('quiz/attempt/<int:attempt_id>/result/', views.quiz_result_view, name='quiz_result'),
]
