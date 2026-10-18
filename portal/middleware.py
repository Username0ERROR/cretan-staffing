from django.http import HttpResponse
from django.urls import reverse


class MaintenanceModeMiddleware:
    """Return a 503 maintenance page while keeping owner recovery routes available."""

    RECOVERY_PREFIXES = (
        '/admin/',
        '/login/',
        '/logout/',
        '/static/',
        '/favicon.ico',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith(self.RECOVERY_PREFIXES):
            return self.get_response(request)

        # Fail open if the database is temporarily unavailable, so an outage
        # in the control lookup does not also lock the owner out of recovery.
        try:
            from .models import PlatformControl
            control = PlatformControl.objects.filter(pk=1).first()
            maintenance = bool(control and control.maintenance_mode)
            message = (
                control.maintenance_message if control
                else 'Cretan Staffing is temporarily undergoing maintenance. Please check back soon.'
            )
        except Exception:
            return self.get_response(request)

        if not maintenance:
            return self.get_response(request)

        response = HttpResponse(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow">'
            '<title>Maintenance | Cretan Staffing</title>'
            '<style>body{margin:0;background:#f4f7fb;color:#1c2b3e;font:16px/1.6 system-ui,sans-serif;'
            'display:grid;min-height:100vh;place-items:center}.card{max-width:620px;margin:24px;padding:42px;'
            'background:#fff;border:1px solid #e2e8f0;border-radius:20px;box-shadow:0 12px 36px #10233f12}'
            '.brand{font-size:12px;letter-spacing:2px;font-weight:800;color:#188b7d}h1{color:#10233f;'
            'font-size:clamp(30px,5vw,44px);line-height:1.1;margin:18px 0}p{color:#68778b}</style></head>'
            '<body><main class="card"><div class="brand">CRETAN STAFFING</div><h1>We’ll be back soon.</h1><p>'
            + __import__('html').escape(message)
            + '</p></main></body></html>',
            status=503,
            content_type='text/html; charset=utf-8',
        )
        response['Retry-After'] = '900'
        response['Cache-Control'] = 'no-store'
        return response
