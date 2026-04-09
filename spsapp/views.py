import json
import os
import subprocess
import random
import string
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Avg, Count, Q, Max, Sum
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic.edit import CreateView
from django.views.decorators.csrf import csrf_exempt
from django import forms
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from .models import Subject, Topic, Resource, Quiz, Question, Choice, QuizAttempt, StudentResponse


# ─────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────

@login_required
def dashboard(request):
    subjects = Subject.objects.filter(teacher=request.user).prefetch_related('topic_set')

    subject_stats = []
    for subject in subjects:
        topics = Topic.objects.filter(subject=subject, teacher=request.user)
        quizzes = Quiz.objects.filter(topic__in=topics)

        total_attempts = QuizAttempt.objects.filter(quiz__in=quizzes, is_completed=True).count()
        # FIX: use percentage-based pass (attempt.percentage >= 70), not raw score
        passed = sum(
            1 for a in QuizAttempt.objects.filter(quiz__in=quizzes, is_completed=True)
            if a.percentage >= 70
        )

        subject_stats.append({
            'subject': subject,
            'topics_count': topics.count(),
            'quizzes_count': quizzes.count(),
            'total_attempts': total_attempts,
            'passed': passed,
        })

    # Recent quizzes with attempt stats
    all_topics = Topic.objects.filter(teacher=request.user)
    recent_quizzes = Quiz.objects.filter(topic__in=all_topics).select_related('topic', 'topic__subject').annotate(
        attempt_count=Count('quizattempt', filter=Q(quizattempt__is_completed=True)),
        avg_score_val=Avg('quizattempt__score', filter=Q(quizattempt__is_completed=True)),
    ).order_by('-created_at')[:10]

    return render(request, 'dashboard.html', {
        'subject_stats': subject_stats,
        'recent_quizzes': recent_quizzes,
        'teacher': request.user,
    })


# ─────────────────────────────────────────
#  SUBJECT CRUD
# ─────────────────────────────────────────

@login_required
def subject_create(request):
    if request.method == 'POST':
        name = request.POST.get('subject_name', '').strip()
        description = request.POST.get('description', '').strip()
        color = request.POST.get('color', '#1a56db').strip()
        if not name:
            messages.error(request, "Fan nomi kiritilishi shart!")
            return redirect('dashboard')
        Subject.objects.create(
            teacher=request.user,
            subject_name=name,
            description=description,
            color=color,
        )
        messages.success(request, f"'{name}' fani muvaffaqiyatli yaratildi!")
    return redirect('dashboard')


@login_required
def subject_edit(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    if request.method == 'POST':
        subject.subject_name = request.POST.get('subject_name', subject.subject_name).strip()
        subject.description = request.POST.get('description', '').strip()
        subject.color = request.POST.get('color', subject.color).strip()
        subject.save()
        messages.success(request, "Fan muvaffaqiyatli yangilandi!")
        return redirect('subjectdetails', subject_name=subject.subject_name)
    return render(request, 'subject_edit.html', {'subject': subject})


@login_required
def subject_delete(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    if request.method == 'POST':
        name = subject.subject_name
        subject.delete()
        messages.success(request, f"'{name}' fani o'chirildi.")
    return redirect('dashboard')


@login_required
def subjectdetails(request, subject_name):
    subject = get_object_or_404(Subject, subject_name=subject_name, teacher=request.user)
    topics = Topic.objects.filter(subject=subject, teacher=request.user).order_by('order', 'created_at')
    return render(request, 'subjectdetails.html', {'topics': topics, 'subject': subject})


# ─────────────────────────────────────────
#  TOPIC CRUD
# ─────────────────────────────────────────

@login_required
def topic_create(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    if request.method == 'POST':
        name = request.POST.get('topic_name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, "Mavzu nomi kiritilishi shart!")
            return redirect('subjectdetails', subject_name=subject.subject_name)
        last_order = Topic.objects.filter(subject=subject).aggregate(m=Max('order'))['m'] or 0
        Topic.objects.create(
            subject=subject,
            teacher=request.user,
            topic_name=name,
            description=description,
            order=last_order + 1,
        )
        messages.success(request, f"'{name}' mavzusi qo'shildi!")
    return redirect('subjectdetails', subject_name=subject.subject_name)


@login_required
def topic_edit(request, topic_uuid):
    topic = get_object_or_404(Topic, topic_uuid=topic_uuid, teacher=request.user)
    if request.method == 'POST':
        topic.topic_name = request.POST.get('topic_name', topic.topic_name).strip()
        topic.description = request.POST.get('description', '').strip()
        topic.save()
        messages.success(request, "Mavzu yangilandi!")
        return redirect('topicdetails', topic_uuid=topic.topic_uuid)
    return render(request, 'topic_edit.html', {'topic': topic})


@login_required
def topic_delete(request, topic_uuid):
    topic = get_object_or_404(Topic, topic_uuid=topic_uuid, teacher=request.user)
    if request.method == 'POST':
        subject_name = topic.subject.subject_name
        topic.delete()
        messages.success(request, "Mavzu o'chirildi.")
        return redirect('subjectdetails', subject_name=subject_name)
    return render(request, 'topic_confirm_delete.html', {'topic': topic})


@login_required
def topic_reorder(request):
    """AJAX: reorder topics via drag-drop. POST JSON: {orders: [{id, order}, ...]}"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            for item in data.get('orders', []):
                Topic.objects.filter(id=item['id'], teacher=request.user).update(order=item['order'])
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=405)


@login_required
def topicdetails(request, topic_uuid):
    topic = get_object_or_404(Topic, topic_uuid=topic_uuid, teacher=request.user)
    resources = Resource.objects.filter(topic=topic, teacher=request.user).order_by('order', 'created_at')
    quizzes = Quiz.objects.filter(topic=topic).annotate(
        attempt_count=Count('quizattempt', filter=Q(quizattempt__is_completed=True)),
        avg_score_ann=Avg('quizattempt__score', filter=Q(quizattempt__is_completed=True)),
    ).order_by('-created_at')
    return render(request, 'topicdetails.html', {
        'topic': topic,
        'resources': resources,
        'quizzes': quizzes,
    })


# ─────────────────────────────────────────
#  RESOURCE CRUD + REORDER
# ─────────────────────────────────────────

@login_required
def resource_viewer(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id, teacher=request.user)
    return render(request, 'resource_viewer.html', {'resource': resource})


@login_required
def resource_delete(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id, teacher=request.user)
    topic_uuid = resource.topic.topic_uuid
    if request.method == 'POST':
        # Delete actual files
        if resource.file:
            try:
                os.remove(resource.file.path)
            except Exception:
                pass
        if resource.pdf_file:
            try:
                os.remove(resource.pdf_file.path)
            except Exception:
                pass
        resource.delete()
        messages.success(request, "Fayl o'chirildi.")
    return redirect('topicdetails', topic_uuid=topic_uuid)


@login_required
def resource_reorder(request):
    """AJAX: reorder resources (slides). POST JSON: {orders: [{id, order}, ...]}"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            for item in data.get('orders', []):
                Resource.objects.filter(id=item['id'], teacher=request.user).update(order=item['order'])
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=405)


class ResourceForm(forms.ModelForm):
    title = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Fayl nomi (ixtiyoriy)'}))

    class Meta:
        model = Resource
        fields = ['title', 'file']

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

        # Set order: last + 1
        last_order = Resource.objects.filter(topic=topic).aggregate(m=Max('order'))['m'] or 0
        resource.order = last_order + 1

        if not resource.title:
            resource.title = os.path.splitext(os.path.basename(resource.file.name))[0]

        resource.save()

        if resource.file_type in ['pptx', 'word']:
            try:
                pdf_path = convert_to_pdf(resource.file.path)
                rel = pdf_path.replace(settings.MEDIA_ROOT + "/", "").replace(settings.MEDIA_ROOT + "\\", "")
                resource.pdf_file = rel
                resource.save()
            except Exception:
                pass

        messages.success(self.request, "Fayl muvaffaqiyatli yuklandi!")
        return redirect('topicdetails', topic_uuid=topic.topic_uuid)


# ─────────────────────────────────────────
#  QUIZ CRUD
# ─────────────────────────────────────────

@login_required
def quiz_list(request):
    """All quizzes for current teacher"""
    topics = Topic.objects.filter(teacher=request.user)
    quizzes = Quiz.objects.filter(topic__in=topics).select_related('topic', 'topic__subject').annotate(
        attempt_count=Count('quizattempt', filter=Q(quizattempt__is_completed=True)),
    ).order_by('-created_at')
    return render(request, 'quiz/quiz_list.html', {'quizzes': quizzes})


@login_required
@transaction.atomic
def create_quiz_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            topic_id = data.get('topic_id')
            topic = get_object_or_404(Topic, id=topic_id, teacher=request.user)

            quiz = Quiz.objects.create(
                topic=topic,
                title=data.get('title', '').strip(),
                description=data.get('description', '').strip(),
                time_limit=int(data.get('time_limit', 15)),
            )
            # Generate session code immediately
            quiz.generate_session_code()

            for order_idx, q_data in enumerate(data.get('questions', [])):
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_data.get('text', '').strip(),
                    question_type=q_data.get('type', 'single'),
                    points=int(q_data.get('points', 5)),
                    order=order_idx,
                    time_limit_seconds=int(q_data.get('time_limit_seconds', 30)),
                )
                for c_idx, c_data in enumerate(q_data.get('choices', [])):
                    Choice.objects.create(
                        question=question,
                        text=c_data.get('text', '').strip(),
                        is_correct=bool(c_data.get('is_correct', False)),
                        order=c_idx,
                    )

            return JsonResponse({
                "status": "success",
                "quiz_uuid": str(quiz.quiz_uuid),
                "take_url": f"/quiz/{quiz.quiz_uuid}/take/",
                "session_code": quiz.session_code,
            })
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    user_topics = Topic.objects.filter(teacher=request.user).select_related('subject')
    return render(request, 'quiz/create_quiz.html', {'user_topics': user_topics})


@login_required
@transaction.atomic
def quiz_edit(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)
    if quiz.topic.teacher != request.user:
        return HttpResponseForbidden("Ruxsat yo'q.")

    if request.method == "POST":
        try:
            data = json.loads(request.body)

            quiz.title = data.get('title', quiz.title).strip()
            quiz.description = data.get('description', '').strip()
            quiz.time_limit = int(data.get('time_limit', quiz.time_limit))
            quiz.save()

            # Clear old questions and rebuild
            quiz.questions.all().delete()
            for order_idx, q_data in enumerate(data.get('questions', [])):
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_data.get('text', '').strip(),
                    question_type=q_data.get('type', 'single'),
                    points=int(q_data.get('points', 5)),
                    order=order_idx,
                    time_limit_seconds=int(q_data.get('time_limit_seconds', 30)),
                )
                for c_idx, c_data in enumerate(q_data.get('choices', [])):
                    Choice.objects.create(
                        question=question,
                        text=c_data.get('text', '').strip(),
                        is_correct=bool(c_data.get('is_correct', False)),
                        order=c_idx,
                    )

            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    questions_data = []
    for q in quiz.questions.prefetch_related('choices').all():
        questions_data.append({
            'id': q.id,
            'text': q.text,
            'type': q.question_type,
            'points': q.points,
            'time_limit_seconds': q.time_limit_seconds,
            'choices': [{'id': c.id, 'text': c.text, 'is_correct': c.is_correct} for c in q.choices.all()],
        })

    user_topics = Topic.objects.filter(teacher=request.user).select_related('subject')
    return render(request, 'quiz/edit_quiz.html', {
        'quiz': quiz,
        'questions_json': json.dumps(questions_data, ensure_ascii=False),
        'user_topics': user_topics,
    })


@login_required
def quiz_delete(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)
    if quiz.topic.teacher != request.user:
        return HttpResponseForbidden()
    topic_uuid = quiz.topic.topic_uuid
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, "Test o'chirildi.")
    return redirect('topicdetails', topic_uuid=topic_uuid)


@login_required
def quiz_regenerate_code(request, quiz_uuid):
    """Invalidate old session, generate new code (expires link)"""
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)
    if quiz.topic.teacher != request.user:
        return HttpResponseForbidden()
    quiz.end_session()
    new_code = quiz.generate_session_code()
    return JsonResponse({'status': 'ok', 'session_code': new_code})


@login_required
def quiz_end_session(request, quiz_uuid):
    """Teacher ends the quiz session — link expires"""
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)
    if quiz.topic.teacher != request.user:
        return HttpResponseForbidden()
    quiz.end_session()
    messages.success(request, "Test sessiyasi yakunlandi. Havola eskirdi.")
    return redirect('quiz_results_admin', quiz_uuid=quiz_uuid)


# ─────────────────────────────────────────
#  EXCEL IMPORT: parse columns -> questions
# ─────────────────────────────────────────

@login_required
def quiz_excel_parse(request):
    """
    POST: multipart with file=excel, column_map JSON
    Returns parsed questions as JSON for frontend to load into quiz form
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)

    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'status': 'error', 'message': 'Fayl yuklanmadi'}, status=400)

    column_map_raw = request.POST.get('column_map', '{}')
    try:
        column_map = json.loads(column_map_raw)
    except Exception:
        column_map = {}

    try:
        wb = openpyxl.load_workbook(uploaded, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return JsonResponse({'status': 'error', 'message': 'Excel fayl bo\'sh'}, status=400)

        headers = [str(h).strip() if h is not None else '' for h in rows[0]]
        data_rows = rows[1:]

        # column_map example:
        # {"question": "Savol", "choice_a": "A javob", "choice_b": "B javob",
        #  "choice_c": "C javob", "choice_d": "D javob", "correct": "To'g'ri javob",
        #  "points": "Ball", "time_limit": "Vaqt (soniya)"}

        def col_idx(key):
            col_name = column_map.get(key, '')
            if col_name in headers:
                return headers.index(col_name)
            return None

        q_idx = col_idx('question')
        if q_idx is None:
            return JsonResponse({'status': 'error', 'message': 'Savol ustuni topilmadi'}, status=400)

        choice_keys = ['choice_a', 'choice_b', 'choice_c', 'choice_d', 'choice_e']
        correct_idx = col_idx('correct')
        points_idx = col_idx('points')
        time_idx = col_idx('time_limit')

        questions = []
        for row in data_rows:
            q_text = str(row[q_idx]).strip() if row[q_idx] else ''
            if not q_text or q_text == 'None':
                continue

            choices = []
            correct_val = str(row[correct_idx]).strip().upper() if correct_idx is not None and row[correct_idx] else ''
            letter_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}

            for i, ck in enumerate(choice_keys):
                cidx = col_idx(ck)
                if cidx is not None and cidx < len(row) and row[cidx]:
                    ctext = str(row[cidx]).strip()
                    if ctext and ctext != 'None':
                        letter = chr(65 + i)  # A, B, C...
                        is_correct = False

                        # Support: "A", "B" or exact text match
                        if correct_val == letter:
                            is_correct = True
                        elif correct_val == ctext.upper():
                            is_correct = True
                        elif correct_val == str(i + 1):  # "1", "2"...
                            is_correct = True

                        choices.append({'text': ctext, 'is_correct': is_correct})

            points = 5
            if points_idx is not None and points_idx < len(row) and row[points_idx]:
                try:
                    points = int(float(row[points_idx]))
                except Exception:
                    pass

            time_seconds = 30
            if time_idx is not None and time_idx < len(row) and row[time_idx]:
                try:
                    time_seconds = int(float(row[time_idx]))
                except Exception:
                    pass

            questions.append({
                'text': q_text,
                'type': 'single',
                'points': points,
                'time_limit_seconds': time_seconds,
                'choices': choices,
            })

        return JsonResponse({'status': 'ok', 'headers': headers, 'questions': questions, 'count': len(questions)})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ─────────────────────────────────────────
#  TAKE QUIZ  (student — no login needed)
# ─────────────────────────────────────────

def take_quiz_view(request, quiz_uuid):
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid, is_active=True)

    # Kahoot-style: session must not be ended
    if quiz.session_ended:
        return render(request, 'quiz/session_expired.html', {'quiz': quiz})

    if request.method == "POST":
        student_name = request.POST.get('student_name', 'Anonim').strip()[:100]

        with transaction.atomic():
            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                student_name=student_name,
                started_at=timezone.now(),
            )

            questions = quiz.questions.prefetch_related('choices').all()
            # Pre-compute max score for this attempt
            max_score = sum(q.points for q in questions)
            total_score = 0.0

            for question in questions:
                selected_ids_raw = request.POST.getlist(f'question_{question.id}')
                try:
                    selected_ids = [int(i) for i in selected_ids_raw]
                except ValueError:
                    selected_ids = []

                # Validate choices belong to this question
                valid_choices = list(
                    question.choices.filter(id__in=selected_ids).values_list('id', flat=True)
                )
                correct_ids = sorted(
                    question.choices.filter(is_correct=True).values_list('id', flat=True)
                )
                is_correct = sorted(valid_choices) == correct_ids and len(correct_ids) > 0
                earned = question.points if is_correct else 0

                resp = StudentResponse.objects.create(
                    attempt=attempt,
                    question=question,
                    is_correct=is_correct,
                    earned_points=earned,
                )
                if valid_choices:
                    resp.selected_choices.set(valid_choices)

                total_score += earned

            attempt.score = total_score
            attempt.max_score = max_score  # CRITICAL FIX: store max score
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

    max_score = attempt.max_score if attempt.max_score > 0 else sum(q.points for q in quiz.questions.all())

    review = []
    for question in quiz.questions.prefetch_related('choices').all():
        try:
            student_resp = attempt.responses.get(question=question)
            selected = set(student_resp.selected_choices.values_list('id', flat=True))
            is_correct = student_resp.is_correct
        except StudentResponse.DoesNotExist:
            selected = set()
            is_correct = False

        correct = set(question.choices.filter(is_correct=True).values_list('id', flat=True))

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
    if quiz.topic.teacher != request.user:
        return HttpResponseForbidden("Ruxsat yo'q.")

    attempts = QuizAttempt.objects.filter(
        quiz=quiz, is_completed=True
    ).order_by('-score', 'completed_at')

    total_students = attempts.count()
    max_score = sum(q.points for q in quiz.questions.all())

    # FIX: use percentage for pass/fail
    passed_count = sum(1 for a in attempts if (a.score / a.max_score * 100 if a.max_score else 0) >= 70)
    failed_count = total_students - passed_count

    avg_raw = attempts.aggregate(avg=Avg('score'))['avg']
    average_score = round(avg_raw, 1) if avg_raw else 0

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
#  LIVE LEADERBOARD (WebSocket alternative: SSE)
# ─────────────────────────────────────────

@login_required
def quiz_live_leaderboard(request, quiz_uuid):
    """Page for teacher to show on big screen — auto-refreshes via SSE"""
    quiz = get_object_or_404(Quiz, quiz_uuid=quiz_uuid)
    if quiz.topic.teacher != request.user:
        return HttpResponseForbidden()
    max_score = sum(q.points for q in quiz.questions.all())
    return render(request, 'quiz/live_leaderboard.html', {
        'quiz': quiz,
        'max_score': max_score,
    })


def quiz_leaderboard_data(request, quiz_uuid):
    """
    SSE endpoint: streams JSON lines of leaderboard every 3 seconds.
    No auth needed — quiz_uuid is the token.
    """
    import time

    def event_stream():
        while True:
            try:
                quiz = Quiz.objects.get(quiz_uuid=quiz_uuid)
                attempts = QuizAttempt.objects.filter(
                    quiz=quiz, is_completed=True
                ).order_by('-score', 'completed_at')[:30]

                max_score = sum(q.points for q in quiz.questions.all())

                data = {
                    'total': attempts.count(),
                    'session_ended': quiz.session_ended,
                    'leaderboard': [
                        {
                            'rank': i + 1,
                            'name': a.student_name,
                            'score': a.score,
                            'max_score': a.max_score if a.max_score else max_score,
                            'percentage': a.percentage,
                        }
                        for i, a in enumerate(attempts)
                    ]
                }
                yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            time.sleep(3)

    response = HttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# ─────────────────────────────────────────
#  EXCEL EXPORT
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

    header_fill = PatternFill(start_color="1a56db", end_color="1a56db", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    center = Alignment(horizontal="center")

    headers = ["#", "O'quvchi ismi", "Ball", "Max ball", "Foiz (%)", "Holat", "Tugatilgan vaqt"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center

    pass_fill = PatternFill(start_color="d1fae5", end_color="d1fae5", fill_type="solid")
    fail_fill = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")

    for row_idx, attempt in enumerate(attempts, 2):
        a_max = attempt.max_score if attempt.max_score > 0 else max_score
        pct = round((attempt.score / a_max) * 100) if a_max else 0
        status = "O'tdi ✓" if pct >= 70 else "Yiqildi ✗"
        row_fill = pass_fill if pct >= 70 else fail_fill
        row_data = [
            row_idx - 1, attempt.student_name, attempt.score, a_max,
            f"{pct}%", status,
            attempt.completed_at.strftime("%d.%m.%Y %H:%M") if attempt.completed_at else "",
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.fill = row_fill
            cell.alignment = center

    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{quiz.title}_natijalar.xlsx"'
    wb.save(response)
    return response
