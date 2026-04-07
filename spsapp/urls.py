from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('subject/<str:subject_name>/', views.subjectdetails, name='subjectdetails'),
    path('topic/<uuid:topic_uuid>/', views.topicdetails, name='topicdetails'),
    path('topic/<uuid:topic_uuid>/upload/', views.ResourceUploadView.as_view(), name='resource_upload'),
    path('resource/<int:resource_id>/view/', views.resource_viewer, name='resource_viewer'),
]