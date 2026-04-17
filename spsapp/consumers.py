"""
WebSocket Consumers for Real-time Leaderboard
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.shortcuts import get_object_or_404
from .models import Quiz, QuizAttempt


class LeaderboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time leaderboard updates
    """
    async def connect(self):
        self.quiz_uuid = self.scope['url_route']['kwargs']['quiz_uuid']
        self.room_group_name = f'leaderboard_{self.quiz_uuid}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial leaderboard data
        leaderboard_data = await self.get_leaderboard_data()
        await self.send(text_data=json.dumps(leaderboard_data))
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming messages (refresh request)"""
        leaderboard_data = await self.get_leaderboard_data()
        await self.send(text_data=json.dumps(leaderboard_data))
    
    async def leaderboard_update(self, event):
        """Receive message from room group"""
        await self.send(text_data=json.dumps(event['data']))
    
    @database_sync_to_async
    def get_leaderboard_data(self):
        """Get current leaderboard data"""
        try:
            quiz = Quiz.objects.get(quiz_uuid=self.quiz_uuid)
            attempts = QuizAttempt.objects.filter(
                quiz=quiz,
                is_completed=True
            ).order_by('-score', 'completed_at')[:30]
            
            max_score = sum(q.points for q in quiz.questions.all())
            
            leaderboard = []
            for idx, attempt in enumerate(attempts, 1):
                leaderboard.append({
                    'rank': idx,
                    'student_name': attempt.student_name,
                    'score': attempt.score,
                    'max_score': attempt.max_score if attempt.max_score else max_score,
                    'percentage': attempt.percentage,
                    'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None
                })
            
            return {
                'type': 'leaderboard_update',
                'total': attempts.count(),
                'session_ended': quiz.session_ended,
                'leaderboard': leaderboard
            }
        except Exception as e:
            return {
                'type': 'error',
                'message': str(e)
            }
