"""Google web reCAPTCHA v2 checkbox, hosted for the native authentication WebView.
No user records, credentials, or clinical information enter this public page.
"""
import json
import secrets
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from .config import settings

router = APIRouter(tags=['Authentication'])
VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


def verify_recaptcha(token: str | None):
    cfg = settings()
    if not cfg.recaptcha_enabled:
        return
    if not token or not token.strip():
        raise HTTPException(403, 'Complete the Google security check first')
    try:
        response = httpx.post(VERIFY_URL,
            data={'secret': cfg.recaptcha_secret_key, 'response': token}, timeout=8.0, follow_redirects=False)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError('Invalid verification response')
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'Google security verification is unavailable. Retry with a new security check.')
    error_codes = result.get('error-codes', [])
    if not isinstance(error_codes, list) or not all(isinstance(code, str) for code in error_codes):
        raise HTTPException(503, 'Google security verification is unavailable. Retry with a new security check.')
    if any(code in ('missing-input-secret', 'invalid-input-secret') for code in error_codes):
        raise HTTPException(503, 'Google security verification is not configured correctly')
    if result.get('success') is not True:
        raise HTTPException(403, 'Security check expired or failed. Complete it again.')
    hostname = result.get('hostname')
    if not isinstance(hostname, str) or hostname.lower() not in cfg.recaptcha_allowed_hostnames:
        raise HTTPException(403, 'Security check was issued for a different application')
    try:
        issued = datetime.fromisoformat(result['challenge_ts'].replace('Z', '+00:00'))
        if issued.tzinfo is None:
            raise ValueError()
        age = (datetime.now(timezone.utc) - issued).total_seconds()
        # Google enforces the token's two-minute, single-use lifetime. challenge_ts
        # is the challenge LOAD time, not necessarily the later token issue time;
        # a person may legitimately need more than two minutes to solve images.
        if age < -30:
            raise ValueError()
    except (KeyError, TypeError, AttributeError, ValueError):
        raise HTTPException(403, 'Security check expired or failed. Complete it again.')


@router.get('/recaptcha-config')
def configuration():
    cfg = settings()
    return {'enabled': cfg.recaptcha_enabled, 'type': 'v2_checkbox',
            'page_url': cfg.recaptcha_public_origin.rstrip('/') + '/api/v1/auth/mobile-recaptcha' if cfg.recaptcha_enabled else None}


@router.get('/mobile-recaptcha', response_class=HTMLResponse)
def checkbox_page():
    cfg = settings()
    if not cfg.recaptcha_enabled:
        raise HTTPException(404, 'Google security verification is disabled')
    nonce = secrets.token_urlsafe(24)
    # The site key is public; the secret must never be included in HTML or JSON.
    site_key = json.dumps(cfg.recaptcha_site_key).replace('<', '\\u003c')
    html = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SehatBridge security verification</title>
<style>body{margin:0;background:#fff9f7;color:#172d3b;font:16px system-ui,sans-serif}
main{padding:20px 8px;display:flex;flex-direction:column;align-items:center;gap:20px}
p{max-width:32rem;text-align:center;line-height:1.5}a{color:#087f75}</style></head>
<body><main><h2>Security verification</h2><p>Complete the “I'm not a robot” checkbox and any challenge below.</p>
<div id="checkbox"></div><p id="status" role="status">Connecting to Google…</p>
<p>Google's <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
and <a href="https://policies.google.com/terms" target="_blank" rel="noopener noreferrer">Terms of Service</a> apply.</p></main>
<script nonce="__NONCE__">
function bridge(message){if(window.ReactNativeWebView){window.ReactNativeWebView.postMessage(JSON.stringify(message));}}
function failed(){document.getElementById('status').textContent='Unable to connect. Close this window and retry.';bridge({type:'error'});}
window.sehatCaptchaReady=function(){try{grecaptcha.render('checkbox',{sitekey:__SITE_KEY__,size:'normal',theme:'light',
callback:function(token){document.getElementById('status').textContent='Check complete. Return to the app.';bridge({type:'token',token:token});},
'expired-callback':function(){document.getElementById('status').textContent='Check expired. Please try again.';bridge({type:'expired'});},
'error-callback':failed});document.getElementById('status').textContent='Please complete the checkbox.';bridge({type:'ready'});}catch(e){failed();}};
</script><script nonce="__NONCE__" src="https://www.google.com/recaptcha/api.js?onload=sehatCaptchaReady&amp;render=explicit" async defer></script>
</body></html>'''.replace('__NONCE__', nonce).replace('__SITE_KEY__', site_key)
    # JS errors are also covered by the native WebView's bounded load timer.
    return HTMLResponse(html, headers={
        'Cache-Control': 'no-store', 'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': f"default-src 'none'; script-src 'nonce-{nonce}' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/; style-src 'unsafe-inline'; frame-src https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/; connect-src https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/; img-src data: https://www.google.com https://www.gstatic.com; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    })
