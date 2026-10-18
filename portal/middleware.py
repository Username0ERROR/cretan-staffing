import json
import os
from html import escape

from django.http import HttpResponse, JsonResponse


class MaintenanceModeMiddleware:
    """
    Owner-account deadlock. An inactive configured owner locks all application
    routes; only the credential-checked owner recovery endpoint and static
    assets remain reachable. API clients receive JSON instead of HTML.
    """

    RECOVERY_PATH = '/owner-recovery/'
    STATIC_PREFIXES = ('/static/', '/favicon.ico')
    DEFAULT_MESSAGE = (
        'Cretan Staffing is temporarily locked for account recovery. '
        'The platform owner must sign in through the secure recovery page.'
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def _lock_state(self):
        owner_username = os.environ.get('STAFF_LOGIN_USERNAME', '').strip()
        message = self.DEFAULT_MESSAGE
        locked = False

        # The owner's is_active flag is the source of truth for the deadlock.
        if owner_username:
            from django.contrib.auth import get_user_model
            owner = get_user_model().objects.filter(username=owner_username).first()
            if owner is None or not owner.is_active:
                locked = True

        # Preserve the existing manual maintenance switch as an additional lock.
        from .models import PlatformControl
        control = PlatformControl.objects.filter(pk=1).first()
        if control and control.maintenance_mode:
            locked = True
            if control.maintenance_message:
                message = control.maintenance_message
        return locked, message

    def _maintenance_response(self, request, message):
        wants_json = (
            request.path.startswith('/api/')
            or 'application/json' in request.headers.get('Accept', '').lower()
        )
        if wants_json:
            response = JsonResponse(
                {'error': 'maintenance_mode', 'detail': message, 'retry_after': 900},
                status=503,
            )
        else:
            response = HttpResponse(
                '<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<meta name="robots" content="noindex,nofollow">'
                '<title>Platform locked | Cretan Staffing</title>'
                '<style>body{margin:0;background:#f4f7fb;color:#1c2b3e;font:16px/1.6 system-ui,sans-serif;'
                'display:grid;min-height:100vh;place-items:center}.card{max-width:620px;margin:24px;padding:42px;'
                'background:#fff;border:1px solid #e2e8f0;border-radius:20px;box-shadow:0 12px 36px #10233f12}'
                '.brand{font-size:12px;letter-spacing:2px;font-weight:800;color:#188b7d}h1{color:#10233f;'
                'font-size:clamp(30px,5vw,44px);line-height:1.1;margin:18px 0}p{color:#68778b}'
                '.btn{display:inline-block;margin-top:14px;padding:12px 18px;background:#10233f;color:white;'
                'text-decoration:none;border-radius:9px;font-weight:700}</style></head><body><main class="card">'
                '<div class="brand">CRETAN STAFFING · SECURITY LOCK</div><h1>Platform temporarily locked.</h1><p>'
                + escape(message)
                + '</p><a class="btn" href="/owner-recovery/">Owner recovery sign-in</a>'
                '</main></body></html>',
                status=503,
                content_type='text/html; charset=utf-8',
            )
        response['Retry-After'] = '900'
        response['Cache-Control'] = 'no-store'
        return response

    def __call__(self, request):
        # Recovery is the sole interactive route available during a deadlock.
        if request.path == self.RECOVERY_PATH or request.path.startswith(self.STATIC_PREFIXES):
            return self.get_response(request)

        try:
            locked, message = self._lock_state()
        except Exception:
            # Fail closed for normal traffic if lock state cannot be checked.
            # Keep recovery reachable so an owner can still attempt recovery.
            return self._maintenance_response(request, self.DEFAULT_MESSAGE)

        if locked:
            return self._maintenance_response(request, message)
        return self.get_response(request)
