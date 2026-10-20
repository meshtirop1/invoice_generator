"""Password-only access gate for the invoice app (everything except /admin/).

Turned on by inv/prod_settings.py, which the live site uses. The password comes only from
the GATE_PASSWORD environment variable (the server's env file): there is no fallback in the
code, so if it is ever missing the gate stays shut instead of opening with a known password.
"""
import hmac
import os

from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.html import escape

GATE_PASSWORD = os.environ.get('GATE_PASSWORD', '')
EXEMPT_PREFIXES = ('/admin/', '/static/')
EXEMPT_EXACT = ('/manifest.json', '/sw.js', '/favicon.ico')

_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>비밀번호</title>
<style>
 *{box-sizing:border-box}
 body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
   background:#0f172a;font-family:-apple-system,'Segoe UI',Roboto,'Malgun Gothic',sans-serif;}
 .card{background:#fff;padding:40px 36px;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.35);
   width:340px;max-width:90vw;text-align:center;}
 h1{margin:0 0 6px;font-size:20px;color:#0f172a;}
 p.sub{margin:0 0 22px;color:#64748b;font-size:13px;}
 input[type=password]{width:100%;padding:15px 16px;font-size:24px;text-align:center;letter-spacing:8px;
   border:2px solid #e2e8f0;border-radius:10px;outline:none;}
 input[type=password]:focus{border-color:#2563eb;}
 button{margin-top:16px;width:100%;padding:13px;font-size:16px;font-weight:700;color:#fff;
   background:#2563eb;border:0;border-radius:10px;cursor:pointer;}
 .err{color:#dc2626;font-size:13px;margin-top:12px;}
</style></head><body>
<form class="card" method="post" action="">
 <h1>비밀번호</h1>
 <p class="sub">Enter password to continue</p>
 <input type="password" name="gate_password" autofocus inputmode="numeric" autocomplete="off">
 <input type="hidden" name="next" value="[[NEXT]]">
 <button type="submit">확인</button>
 [[ERR]]
</form></body></html>"""


def password_ok(typed):
    """True only for the configured password, compared in constant time; never when unset."""
    return bool(GATE_PASSWORD) and hmac.compare_digest(typed.encode(), GATE_PASSWORD.encode())


class GatePasswordMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if (request.session.get('inv_gate_ok')
                or path.startswith(EXEMPT_PREFIXES)
                or path in EXEMPT_EXACT):
            return self.get_response(request)
        if request.method == 'POST' and 'gate_password' in request.POST:
            if password_ok(request.POST.get('gate_password', '')):
                request.session['inv_gate_ok'] = True
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
                return redirect('/')  # always land on home after login
            return HttpResponse(_PAGE.replace('[[NEXT]]', escape(request.POST.get('next', '/') or '/'))
                                     .replace('[[ERR]]', '<p class="err">비밀번호가 틀렸습니다.</p>'))
        return HttpResponse(_PAGE.replace('[[NEXT]]', escape(request.get_full_path()))
                                 .replace('[[ERR]]', ''))
