import json
import os
import subprocess
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic.edit import CreateView
from django import forms
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from .models import Subject, Topic, Resource, Quiz, Question, Choice, QuizAttempt, StudentResponse


# ─────────────────────────────────────────
#  HELPER DECORATORS / GUARDS
# ─────────────────────────────────────────

def teacher_required(view_func):
    """Only authenticated staff/superuser OR teachers (has subjects) can pass."""
    from functools import wraps

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        return view_func(request, *args, **kwargs)

    return _wrapped


# ─────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────

@login_required
def dashboard(request):
    subjects = Subject.objects.filter(teacher=request.user).prefetch_related('topic_set')

    # Per-subject quiz stats
    subject_stats = []
    for subject in subjects:
        topics = Topic.objects.filter(subject=subject, teacher=request.user)
        quizzes = Quiz.objects.filter(topic__in=topics, topic__teacher=request.user)

        total_attempts = QuizAttempt.objects.filter(quiz__in=quizzes, is_completed=True).count()
        passed = QuizAttempt.objects.filter(quiz__in=quizzes, is_completed=True, score__gte=70).count()

        subject_stats.append({
            'subject': subject,
            'topics_count': topics.count(),
            'quizzes_count': quizzes.count(),
            'total_attempts': total_attempts,
            'passed': passed,
        })

    return render(request, 'dashboard.html', {
        'subject_stats': subject_stats,
        'teacher': request.user,
    })


# ─────────────────────────────────────────
#  SUBJECT / TOPIC
# ─────────────────────────────────────────

@login_required
def subjectdetails(request, subject_name):
    subject = get_object_or_404(Subject, subject_name=subject_name, teacher=request.user)
    topics = Topic.objects.filter(subject=subject, teacher=request.user).order_by('order')
    return render(request, 'subjectdetails.html', {'topics': topics, 'subject': subject})


@login_required
def topicdetails(request, topic_uuid):
    topic = get_object_or_404(Topic, topic_uuid=topic_uuid, teacher=request.user)
    resources = Resource.objects.filter(topic=topic, teacher=request.user).order_by('-created_at')
    quizzes = Quiz.objects.filter(topic=topic).annotate(
        attempt_count=Count('quizattempt', filter=Q(quizattempt__is_completed=True)),
        avg_score=Avg('quizattempt__score', filter=Q(quizattempt__is_completed=True)),
    )
    return render(request, 'topicdetails.html', {
        'topic': topic,
        'resources': resources,
        'quizzes': quizzes,
    })


# ─────────────────────────────────────────
#  RESOURCE UPLOAD / VIEW
# ─────────────────────────────────────────

@login_required
def resource_viewer(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id, teacher=request.user)
    return render(request, 'resource_viewer.html', {'resource': resource})


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ['file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.update({'class': 'form-control'})


def convert_to_pdf(input_path):
    output_dir = os.path.dirname(input_path)
    subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", input_path, "--outdir", output_dir],
        capture_output=True, timeout=60
    )
    base = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(output_dir, base + ".pdf")


class ResourceUploadView(LoginRequiredMixin, CreateView):
    model = Resource
    form_class = ResourceForm
    template_name = 'resource_upload.html'

    def form_valid(self, form):
        topic = get_object_or_404(Topic, topic_uuid=self.kwargs['topic_uuid'], teacher=self.request.user)
        resource = form.save(commit=False)
        resource.topic = topic
        resource.teacher = self.request.user

        name = resource.file.name.lower()
        if name.endswith('.pdf'):
            resource.file_type = 'pdf'
        elif name.endswith(('.ppt', '.pptx')):
            resource.file_type = 'pptx'
        elif name.endswith(('.doc', '.docx')):
            resource.file_type = 'word'
        else:
            resource.file_type = 'other'

        resource.save()

        if resource.file_type in ['pptx', 'word']:
            try:
                pdf_path = convert_to_pdf(resource.file.path)
                resource.pdf_file = pdf_path.replace(settings.MEDIA_ROOT + "/", "")
                resource.save()
            except Exception:
                pass  # Conversion failed gracefully

        return redirect('topicdetails', topic_uuid=topic.topic_uuid)


# ─────────────────────────────────────────
#  QUIZ CREATE  (teacher only)
# ─────────────────────────────────────────

@login_required
@transaction.atomic
def create_quiz_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            topic_id = data.get('topic_id')
            # Security: make sure topic belongs to this teacher
            topic = get_object_or_404(Topic, id=topic_id, teacher=request.user)

            quiz = Quiz.objects.create(
                topic=topic,
                title=data.get('title', '').strip(),
                description=data.get('description', '').strip(),
                time_limit=int(data.get('time_limit', 15)),
            )

            for order_idx, q_data in enumerate(data.get('questions', [])):
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_data.get('text', '').strip(),
                    question_type=q_data.get('type', 'single'),
                    points=int(q_data.get('points', 5)),
                    order=order_idx,
                )
                for c_data in q_data.get('choices', []):
                    Choice.objects.create(
                        question=question,
                        text=c_data.get('text', '').strip(),
                        is_correct=bool(c_data.get('is_correct', False)),
                    )

            return JsonResponse({
                "status": "success",
                "quiz_uuid": str(quiz.quiz_uuid),
                "take_url": f"/quiz/{quiz.quiz_uuid}/take/",
            })

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    user_topics = Topic.objects.filter(teacher=request.user).select_related('subject')
    return render(request, 'quiz/create_quiz.html', {'user_topics': user_topics})


# ─────────────────────────────────────────
#  TAKE QUIZ  (student — no login needed)
# ─────────────────────────────────────────

def take_quiz_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid, is_active=True)

    if request.method == "POST":
        student_name = request.POST.get('student_name', 'Anonim').strip()[:100]

        with transaction.atomic():
            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                student_name=student_name,
                started_at=timezone.now(),
            )

            total_score = 0
            questions = quiz.questions.prefetch_related('choices').all()

            for question in questions:
                selected_ids_raw = request.POST.getlist(f'question_{question.id}')
                try:
                    selected_ids = [int(i) for i in selected_ids_raw]
                except ValueError:
                    selected_ids = []

                if selected_ids:
                    # Validate choices belong to this question (prevent tampering)
                    valid_choices = list(
                        question.choices.filter(id__in=selected_ids).values_list('id', flat=True)
                    )
                    if valid_choices:
                        resp = StudentResponse.objects.create(attempt=attempt, question=question)
                        resp.selected_choices.set(valid_choices)

                        correct_ids = sorted(
                            question.choices.filter(is_correct=True).values_list('id', flat=True)
                        )
                        if sorted(valid_choices) == correct_ids:
                            total_score += question.points

            attempt.score = total_score
            attempt.is_completed = True
            attempt.completed_at = timezone.now()
            attempt.save()

        return redirect('quiz_result', attempt_id=attempt.id)

    return render(request, 'quiz/take_quiz.html', {'quiz': quiz})


# ─────────────────────────────────────────
#  QUIZ RESULT  (student review)
# ─────────────────────────────────────────

def quiz_result_view(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, is_completed=True)
    quiz = attempt.quiz

    # Max possible score
    max_score = sum(q.points for q in quiz.questions.all())

    # Build review data
    review = []
    for question in quiz.questions.prefetch_related('choices').all():
        try:
            student_resp = attempt.responses.get(question=question)
            selected = set(student_resp.selected_choices.values_list('id', flat=True))
        except StudentResponse.DoesNotExist:
            selected = set()

        correct = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
        is_correct = selected == correct

        review.append({
            'question': question,
            'choices': question.choices.all(),
            'selected': selected,
            'correct': correct,
            'is_correct': is_correct,
        })

    percentage = round((attempt.score / max_score) * 100) if max_score > 0 else 0

    return render(request, 'quiz/result.html', {
        'attempt': attempt,
        'quiz': quiz,
        'review': review,
        'max_score': max_score,
        'percentage': percentage,
        'passed': percentage >= 70,
    })


# ─────────────────────────────────────────
#  QUIZ RESULTS ADMIN  (teacher leaderboard)
# ─────────────────────────────────────────

@login_required
def quiz_results_admin(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)

    # Security: only topic owner can see results
    if quiz.topic.teacher != request.user:
        return HttpResponseForbidden("Ruxsat yo'q.")

    attempts = QuizAttempt.objects.filter(
        quiz=quiz, is_completed=True
    ).order_by('-score', 'completed_at')

    total_students = attempts.count()
    stats = attempts.aggregate(avg=Avg('score'))
    average_score = round(stats['avg'], 1) if stats['avg'] else 0
    passed_count = attempts.filter(score__gte=70).count()
    failed_count = total_students - passed_count

    # Max possible score for percentage column
    max_score = sum(q.points for q in quiz.questions.all())

    return render(request, 'quiz/admin_results.html', {
        'quiz': quiz,
        'attempts': attempts,
        'total_students': total_students,
        'average_score': average_score,
        'passed_count': passed_count,
        'failed_count': failed_count,
        'max_score': max_score,
    })


# ─────────────────────────────────────────
#  EXCEL EXPORT  (teacher only)
# ─────────────────────────────────────────

@login_required
def export_results_excel(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)

    if quiz.topic.teacher != request.user:
        return HttpResponseForbidden("Ruxsat yo'q.")

    attempts = QuizAttempt.objects.filter(quiz=quiz, is_completed=True).order_by('-score')
    max_score = sum(q.points for q in quiz.questions.all())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Natijalar"

    # Header styling
    header_fill = PatternFill(start_color="1a56db", end_color="1a56db", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    center = Alignment(horizontal="center")

    headers = ["#", "O'quvchi ismi", "Ball", "Max ball", "Foiz (%)", "Holat", "Tugatilgan vaqt"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center

    # Data rows
    pass_fill = PatternFill(start_color="d1fae5", end_color="d1fae5", fill_type="solid")
    fail_fill = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")

    for row_idx, attempt in enumerate(attempts, 2):
        pct = round((attempt.score / max_score) * 100) if max_score else 0
        status = "O'tdi ✓" if pct >= 70 else "Yiqildi ✗"
        row_fill = pass_fill if pct >= 70 else fail_fill
        row_data = [
            row_idx - 1,
            attempt.student_name,
            attempt.score,
            max_score,
            f"{pct}%",
            status,
            attempt.completed_at.strftime("%d.%m.%Y %H:%M") if attempt.completed_at else "",
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.fill = row_fill
            cell.alignment = center

    # Column widths
    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{quiz.title}_natijalar.xlsx"'
    wb.save(response)
    return response
