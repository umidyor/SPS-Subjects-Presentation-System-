"""
views_context_helpers.py
========================
Har bir Django view uchun sps_data_json context ni tayyorlash.

ISHLATISH:
  from .views_context_helpers import subject_stats_json, topic_list_json, ...

  def dashboard(request):
      ...
      return render(request, 'dashboard.html', {
          'sps_data_json': subject_stats_json(request, subject_stats, recent_quizzes),
      })
"""
import json
from django.core.serializers.json import DjangoJSONEncoder


def _dumps(data):
    return json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False)


# ── Dashboard ─────────────────────────────────────────────────────────────────
def dashboard_json(request, subject_stats, recent_quizzes):
    """
    subject_stats: list of dicts (from views.dashboard)
    recent_quizzes: queryset with annotated attempt_count, avg_score_val
    """
    stats_list = []
    for item in subject_stats:
        s = item['subject']
        stats_list.append({
            'subject': {
                'id':           s.id,
                'subject_name': s.subject_name,
                'description':  s.description or '',
                'color':        s.color,
            },
            'topics_count':   item['topics_count'],
            'quizzes_count':  item['quizzes_count'],
            'total_attempts': item['total_attempts'],
            'passed':         item['passed'],
        })

    quizzes_list = []
    for q in recent_quizzes:
        quizzes_list.append({
            'quiz_uuid':                  str(q.quiz_uuid),
            'title':                      q.title,
            'time_limit':                 q.time_limit,
            'session_ended':              q.session_ended,
            'session_code':               q.session_code or '',
            'attempt_count':              q.attempt_count or 0,
            'avg_score_val':              round(q.avg_score_val, 1) if q.avg_score_val else None,
            'topic__topic_name':          q.topic.topic_name,
            'topic__subject__subject_name': q.topic.subject.subject_name,
        })

    return _dumps({
        'teacher': {
            'id':         request.user.id,
            'username':   request.user.username,
            'first_name': request.user.first_name,
        },
        'subject_stats': stats_list,
        'recent_quizzes': quizzes_list,
    })


# ── Subject Detail ────────────────────────────────────────────────────────────
def subject_detail_json(request, subject, topics):
    """
    topics: queryset of Topic with annotated resource_count, quiz_count (yoki oddiy queryset)
    """
    topics_list = []
    for t in topics:
        topics_list.append({
            'id':            t.id,
            'topic_uuid':    str(t.topic_uuid),
            'topic_name':    t.topic_name,
            'description':   t.description or '',
            'order':         t.order,
            'created_at':    t.created_at.strftime('%d.%m.%Y'),
            'resource_count': getattr(t, 'resource_count', 0),
            'quiz_count':     getattr(t, 'quiz_count', 0),
        })

    return _dumps({
        'subject': {
            'id':           subject.id,
            'subject_name': subject.subject_name,
            'description':  subject.description or '',
            'color':        subject.color,
        },
        'topics': topics_list,
    })


# ── Topic Detail ──────────────────────────────────────────────────────────────
def topic_detail_json(request, topic, resources, quizzes):
    resources_list = []
    for r in resources:
        resources_list.append({
            'id':        r.id,
            'title':     r.title or '',
            'file_type': r.file_type,
            'file_url':  r.file.url if r.file else '',
            'pdf_url':   r.pdf_file.url if r.pdf_file else '',
            'order':     r.order,
        })

    quizzes_list = []
    for q in quizzes:
        quizzes_list.append({
            'quiz_uuid':    str(q.quiz_uuid),
            'title':        q.title,
            'time_limit':   q.time_limit,
            'session_code': q.session_code or '',
            'session_ended':q.session_ended,
            'attempt_count': getattr(q, 'attempt_count', 0),
            'avg_score':    round(getattr(q, 'avg_score_ann', 0) or 0, 1),
        })

    return _dumps({
        'topic': {
            'id':         topic.id,
            'topic_uuid': str(topic.topic_uuid),
            'topic_name': topic.topic_name,
            'subject': {
                'subject_name': topic.subject.subject_name,
                'color':        topic.subject.color,
            },
        },
        'resources': resources_list,
        'quizzes':   quizzes_list,
    })


# ── Quiz Results (Admin) ──────────────────────────────────────────────────────
def quiz_results_json(request, quiz, attempts, stats):
    """
    stats: dict with total_students, average_score, passed_count, failed_count, max_score
    """
    attempts_list = []
    for a in attempts:
        attempts_list.append({
            'id':            a.id,
            'student_name':  a.student_name,
            'score':         a.score,
            'max_score':     a.max_score,
            'percentage':    a.percentage,
            'completed_at':  a.completed_at.strftime('%d.%m.%Y %H:%M') if a.completed_at else '',
        })

    return _dumps({
        'quiz': {
            'quiz_uuid':    str(quiz.quiz_uuid),
            'title':        quiz.title,
            'time_limit':   quiz.time_limit,
            'session_code': quiz.session_code or '',
            'session_ended':quiz.session_ended,
        },
        'attempts': attempts_list,
        'stats': stats,
    })


# ── Create Quiz ───────────────────────────────────────────────────────────────
def create_quiz_json(request, topics):
    topics_list = []
    for t in topics:
        topics_list.append({
            'id':         t.id,
            'topic_name': t.topic_name,
            'subject_name': t.subject.subject_name,
        })
    return _dumps({'topics': topics_list})


# ── Edit Quiz ─────────────────────────────────────────────────────────────────
def edit_quiz_json(request, quiz, topics, questions_data):
    """questions_data: already-serialized list (from quiz_edit view)"""
    topics_list = [{'id':t.id,'topic_name':t.topic_name,'subject_name':t.subject.subject_name} for t in topics]
    return _dumps({
        'quiz': {
            'quiz_uuid':   str(quiz.quiz_uuid),
            'title':       quiz.title,
            'description': quiz.description or '',
            'time_limit':  quiz.time_limit,
            'topic_id':    quiz.topic_id,
        },
        'questions': questions_data,
        'topics':    topics_list,
    })


# ── Live Leaderboard ──────────────────────────────────────────────────────────
def live_leaderboard_json(request, quiz, max_score):
    return _dumps({
        'quiz': {
            'quiz_uuid':    str(quiz.quiz_uuid),
            'title':        quiz.title,
            'session_ended':quiz.session_ended,
        },
        'max_score': max_score,
        'leaderboard_data_url': f'/quiz/{quiz.quiz_uuid}/leaderboard-data/',
    })


# ── Take Quiz (Student) ───────────────────────────────────────────────────────
def take_quiz_json(quiz):
    questions_list = []
    for q in quiz.questions.prefetch_related('choices').all():
        questions_list.append({
            'id':                 q.id,
            'text':               q.text,
            'image_url':          q.image.url if q.image else '',
            'question_type':      q.question_type,
            'points':             q.points,
            'time_limit_seconds': q.time_limit_seconds,
            'choices': [{'id':c.id,'text':c.text,'order':c.order} for c in q.choices.all()],
        })
    return _dumps({
        'quiz': {
            'quiz_uuid':    str(quiz.quiz_uuid),
            'title':        quiz.title,
            'time_limit':   quiz.time_limit,
            'session_code': quiz.session_code or '',
            'questions':    questions_list,
        }
    })


# ── Quiz Result (Student) ─────────────────────────────────────────────────────
def quiz_result_json(attempt, quiz, review, percentage, passed):
    review_list = []
    for item in review:
        review_list.append({
            'question_text': item['question'].text,
            'is_correct':    item['is_correct'],
            'selected_ids':  list(item['selected']),
            'correct_ids':   list(item['correct']),
            'choices': [{'id':c.id,'text':c.text} for c in item['choices']],
        })
    return _dumps({
        'attempt': {
            'id':           attempt.id,
            'student_name': attempt.student_name,
            'score':        attempt.score,
            'max_score':    attempt.max_score,
            'percentage':   percentage,
            'completed_at': attempt.completed_at.strftime('%d.%m.%Y %H:%M') if attempt.completed_at else '',
        },
        'quiz': {
            'quiz_uuid': str(quiz.quiz_uuid),
            'title':     quiz.title,
        },
        'review':     review_list,
        'passed':     passed,
        'percentage': percentage,
    })
