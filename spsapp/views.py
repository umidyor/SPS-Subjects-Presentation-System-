from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Subject, Topic, Resource
from django import forms


# Dashboard (mavjud)
@login_required
def dashboard(request):
    subjects = Subject.objects.filter(teacher=request.user)
    return render(request, 'dashboard.html', {'subjects': subjects, 'teacher': request.user})


# Fan detallari (mavjud, biroz o'zgartirilgan)
@login_required
def subjectdetails(request, subject_name):
    subject = get_object_or_404(Subject, subject_name=subject_name, teacher=request.user)
    topics = Topic.objects.filter(subject=subject, teacher=request.user).order_by('order')
    return render(request, 'subjectdetails.html', {'topics': topics, 'subject': subject})


# Mavzu detallari (fayllar ro'yxati)
@login_required
def topicdetails(request, topic_uuid):
    topic = get_object_or_404(Topic, topic_uuid=topic_uuid, teacher=request.user)
    resources = Resource.objects.filter(topic=topic, teacher=request.user).order_by('-created_at')
    return render(request, 'topicdetails.html', {'topic': topic, 'resources': resources})


# Fayl ko'rsatish (Viewer)
@login_required
def resource_viewer(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id, teacher=request.user)
    return render(request, 'resource_viewer.html', {'resource': resource})


# ModelForm fayl yuklash uchun
class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ['file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.update({'class': 'form-control'})


# CreateView fayl yuklash uchun
class ResourceUploadView(LoginRequiredMixin, CreateView):
    model = Resource
    form_class = ResourceForm
    template_name = 'resource_upload.html'

    def form_valid(self, form):
        topic = get_object_or_404(Topic, topic_uuid=self.kwargs['topic_uuid'], teacher=self.request.user)
        resource = form.save(commit=False)
        resource.topic = topic
        resource.teacher = self.request.user

        # Fayl turini aniqlash
        file_name = resource.file.name.lower()
        if file_name.endswith('.pdf'):
            resource.file_type = 'pdf'
        elif file_name.endswith('.pptx') or file_name.endswith('.ppt'):
            resource.file_type = 'pptx'
        elif file_name.endswith('.docx') or file_name.endswith('.doc'):
            resource.file_type = 'word'
        else:
            resource.file_type = 'other'

        resource.save()
        return redirect('topicdetails', topic_uuid=topic.topic_uuid)