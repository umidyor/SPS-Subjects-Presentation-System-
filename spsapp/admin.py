
from django.contrib import admin

from spsapp.models import *
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('subject_name',)
    search_fields = ('subject_name',)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('topic_name',)
    search_fields = ('topic_name',)

@admin.register(Resource)
class FileAdmin(admin.ModelAdmin):
    list_display = ('file_type',)




