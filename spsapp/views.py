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
import subprocess
import os
from django.conf import settings


def convert_to_pdf(input_path):
    output_dir = os.path.dirname(input_path)

    # LibreOffice buyrug'i
    result = subprocess.run([
        "libreoffice", "--headless", "--convert-to", "pdf",
        input_path, "--outdir", output_dir
    ], capture_output=True)


    file_base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(output_dir, file_base_name + ".pdf")

    return pdf_path

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
        elif file_name.endswith(('.ppt', '.pptx')):
            resource.file_type = 'pptx'

        elif file_name.endswith(('.doc', '.docx')):
            resource.file_type = 'word'

        else:
            resource.file_type = 'other'

        resource.save()

        # PPT / DOC bo‘lsa PDF ga convert qilamiz
        if resource.file_type in ['pptx', 'word']:
            input_path = resource.file.path
            pdf_path = convert_to_pdf(input_path)

            resource.pdf_file = pdf_path.replace(settings.MEDIA_ROOT + "/", "")
            resource.save()

        return redirect('topicdetails', topic_uuid=topic.topic_uuid)


import json
from django.http import JsonResponse
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import Quiz, Question, Choice

@login_required
@transaction.atomic
def create_quiz_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            
            # Quiz yaratish...
            quiz = Quiz.objects.create(
                topic_id=data.get('topic_id'),
                title=data.get('title'),
                description=data.get('description', ''),
                time_limit=data.get('time_limit', 15)
            )

            # Savollarni yaratish...
            for q_data in data.get('questions', []):
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_data.get('text'),
                    question_type=q_data.get('type', 'single'),
                    points=q_data.get('points', 5),
                    order=q_data.get('order', 0)
                )

                # Variantlarni yaratish...
                for c_data in q_data.get('choices', []):
                    Choice.objects.create(
                        question=question,
                        text=c_data.get('text'),
                        is_correct=c_data.get('is_correct', False)
                    )

            return JsonResponse({
                "status": "success",
                "message": "Test muvaffaqiyatli yaratildi!",
                "quiz_id": quiz.id
            })

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    # FAQAT shu o'qituvchiga (login qilgan userga) tegishli topiclarni olish
    # 'author' maydoni o'rniga o'zingizni modelingizdagi maydon nomini yozing
    user_topics = Topic.objects.filter(teacher=request.user) 
    
    return render(request, 'create_quiz.html', context={'user_topics': user_topics})

from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from .models import Quiz, Question, Choice, QuizAttempt, StudentResponse

def take_quiz_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)
    
    if request.method == "POST":
        # 1. Urinishni yaratamiz (o'quvchi ismi bilan)
        student_name = request.POST.get('student_name', 'Anonim')
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_name=student_name,
            started_at=timezone.now()
        )
        
        total_score = 0
        questions = quiz.questions.all()
        
        for question in questions:
            # Har bir savol uchun tanlangan javob(lar)ni olamiz
            selected_choice_ids = request.POST.getlist(f'question_{question.id}')
            
            if selected_choice_ids:
                # StudentResponse yaratish
                response = StudentResponse.objects.create(attempt=attempt, question=question)
                response.selected_choices.set(selected_choice_ids)
                
                # Ballni hisoblash mantiqi
                correct_choices = list(question.choices.filter(is_correct=True).values_list('id', flat=True))
                selected_ids = [int(i) for i in selected_choice_ids]
                
                # Agar hamma to'g'ri javoblar to'liq tanlangan bo'lsa
                if sorted(correct_choices) == sorted(selected_ids):
                    total_score += question.points
        
        # Urinishni yakunlaymiz
        attempt.score = total_score
        attempt.is_completed = True
        attempt.completed_at = timezone.now()
        attempt.save()
        
        return render(request, 'quiz/result.html', {'attempt': attempt})

    # GET so'rovi: Savollarni ko'rsatish
    return render(request, 'quiz/take_quiz.html', {'quiz': quiz})


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Quiz, QuizAttempt

@login_required
def quiz_results_admin(request, quiz_uuid):
    # 1. Testni bazadan qidirib topamiz
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)
    
    # 2. Shu testga tegishli barcha yakunlangan urinishlarni olamiz
    # Eng yuqori ballni birinchi qilib tartiblaymiz (-score)
    attempts = QuizAttempt.objects.filter(
        quiz=quiz, 
        is_completed=True
    ).order_by('-score', 'completed_at')
    
    # 3. Ba'zi statistikalar (ixtiyoriy, lekin foydali)
    total_students = attempts.count()
    average_score = 0
    if total_students > 0:
        # Hamma ballarni qo'shib, talabalar soniga bo'lamiz
        from django.db.models import Avg
        average_score = attempts.aggregate(Avg('score'))['score__avg']

    context = {
        'quiz': quiz,
        'attempts': attempts,
        'total_students': total_students,
        'average_score': round(average_score, 1) if average_score else 0
    }
    
    return render(request, 'quiz/admin_results.html', context)
