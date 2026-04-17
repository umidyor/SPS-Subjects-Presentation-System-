"""
Security Middleware for SPS API
Additional security layers beyond Django defaults
"""
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses
    """
    def process_response(self, request, response):
        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Enable XSS protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions policy
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware
    For production, use django-ratelimit or similar
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.request_counts = {}
    
    def __call__(self, request):
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Check if IP is making too many requests
        # This is a simple example - use Redis in production
        if ip in self.request_counts:
            if self.request_counts[ip] > 100:  # 100 requests per minute
                logger.warning(f"Rate limit exceeded for IP: {ip}")
                return HttpResponse('Rate limit exceeded', status=429)
            self.request_counts[ip] += 1
        else:
            self.request_counts[ip] = 1
        
        response = self.get_response(request)
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Log all requests for security monitoring
    """
    def process_request(self, request):
        # Log request details
        logger.info(
            f"Request: {request.method} {request.path} "
            f"from {request.META.get('REMOTE_ADDR')} "
            f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}"
        )
        return None
    
    def process_response(self, request, response):
        # Log response status
        logger.info(
            f"Response: {request.method} {request.path} "
            f"Status: {response.status_code}"
        )
        return response
