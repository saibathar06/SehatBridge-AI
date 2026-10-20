"""Generate development secrets once. Does not overwrite existing configuration."""
import base64
import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / '.env'
if target.exists():
    print('Existing backend/.env preserved')
else:
    template = target.with_name('.env.example').read_text()
    for field in ('JWT_SECRET', 'OTP_SECRET'):
        template = template.replace(f'{field}=GENERATE_ME', f'{field}={secrets.token_urlsafe(48)}')
    template = template.replace('ENCRYPTION_KEY=GENERATE_ME', 'ENCRYPTION_KEY=' + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    target.write_text(template)
    print('Created backend/.env with unique development secrets')
