from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, delete
from sqlalchemy.exc import IntegrityError
from .config import settings
from .db import session, SessionLocal
from .models import Profile, User, Page, Document, Chat, Conversation, Device, now
from .schemas import ProfileInput, ChatInput
from .security import current_user, read, put, audit, sensitive_limit, limiter
from .patient_context_service import patient_context
from .question_router_service import answer_question
from .storage import remove
from . import auth, documents, treatments, notifications, demo
from .body_limit import BodyLimitMiddleware


@asynccontextmanager
async def lifespan(app):
    # Schema creation belongs to Alembic, never to web process startup.
    yield


app = FastAPI(title='SehatBridge AI', version='1.0.0', lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware, max_bytes=(settings().max_upload_mb + 1) * 1024 * 1024)
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins,
                   allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
                   allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'])


@app.middleware('http')
async def guard(request: Request, call_next):
    if request.url.path.startswith('/api/'):
        try:
            limiter.check('global:' + (request.client.host if request.client else 'unknown'), settings().rate_limit_per_minute)
        except HTTPException as error:
            return JSONResponse({'error': {'code': error.status_code, 'message': error.detail}}, error.status_code, headers=error.headers)
    length = request.headers.get('content-length')
    if length and (not length.isdigit() or int(length) > (settings().max_upload_mb + 1) * 1024 * 1024):
        return JSONResponse({'error': {'code': 413, 'message': 'Payload exceeds size limit'}}, 413)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    if settings().environment == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return JSONResponse({'error': {'code': error.status_code, 'message': error.detail}}, error.status_code, headers=error.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Avoid echoing passwords, tokens or medical content from Pydantic error input.
    fields = ['.'.join(str(p) for p in e['loc']) for e in error.errors()]
    return JSONResponse({'error': {'code': 422, 'message': 'Invalid input', 'fields': fields}}, 422)


@app.exception_handler(IntegrityError)
async def conflict_error(request, error):
    return JSONResponse({'error': {'code': 409, 'message': 'Record changed or already exists. Reload and retry.'}}, 409)


@app.exception_handler(Exception)
async def internal_error(request, error):
    return JSONResponse({'error': {'code': 500, 'message': 'Request could not be completed'}}, 500)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/ready')
def ready(db=Depends(session)):
    db.execute(text('SELECT 1'))
    db.execute(select(User.id).limit(1))
    if settings().redis_url:
        try:
            limiter.redis.ping()
        except Exception:
            raise HTTPException(503, 'Redis unavailable')
    return {'status': 'ready'}


api = APIRouter(prefix='/api/v1')
for route in (auth.router, documents.router, treatments.router, notifications.router, demo.router):
    api.include_router(route)


@api.get('/profile', tags=['Profile'])
def profile(user=Depends(current_user), db=Depends(session)):
    return {'id': user.id, **read(db.scalar(select(Profile).where(Profile.user_id == user.id)))}


@api.put('/profile', tags=['Profile'])
def update_profile(body: ProfileInput, user=Depends(current_user), db=Depends(session)):
    row = db.scalar(select(Profile).where(Profile.user_id == user.id).with_for_update())
    previous = read(row)
    put(row, body.model_dump())
    if previous['chat_history'] and not body.chat_history:
        db.execute(delete(Chat).where(Chat.user_id == user.id))
        db.execute(delete(Conversation).where(Conversation.user_id == user.id))
    audit(db, user.id, 'profile_updated')
    return {'id': user.id, **read(row)}


@api.get('/dashboard', tags=['Patient'])
def dashboard(user=Depends(current_user), db=Depends(session)):
    context = patient_context(db, user.id)
    from .documents import document_view
    context['documents'] = [document_view(db, d) for d in db.scalars(select(Document).where(Document.user_id == user.id))]
    context['counts'] = {s: sum(1 for d in context['doses'] if d['status'] == s) for s in ('taken', 'upcoming', 'missed', 'skipped')}
    return context


@api.post('/chat', tags=['Assistant'])
def chat(body: ChatInput, request: Request, user=Depends(current_user), db=Depends(session)):
    sensitive_limit(request, user.id, 'chat', 15)
    context = patient_context(db, user.id)
    response = answer_question(body.question, body.language, context, body.document_id)
    if context['profile']['chat_history']:
        conversation = db.scalar(select(Conversation).where(Conversation.user_id == user.id))
        if not conversation:
            conversation = put(Conversation(user_id=user.id), {'created_at': now()})
            db.add(conversation)
            db.flush()
        db.add(put(Chat(user_id=user.id, conversation_id=conversation.id), {'question': body.question, **response, 'language': body.language, 'created_at': now()}))
    return response


@api.get('/chat', tags=['Assistant'])
def chat_history(user=Depends(current_user), db=Depends(session)):
    # Bound response memory; conversations are opt-in encrypted entries.
    messages = db.scalars(select(Chat).where(Chat.user_id == user.id).order_by(Chat.created_at.desc()).limit(100)).all()
    return [{'id': c.id, **read(c)} for c in reversed(messages)]


@api.delete('/chat', tags=['Assistant'])
def clear_chat(user=Depends(current_user), db=Depends(session)):
    db.execute(delete(Chat).where(Chat.user_id == user.id))
    db.execute(delete(Conversation).where(Conversation.user_id == user.id))
    return {'message': 'Chat history deleted'}


@api.get('/speech/capabilities', tags=['Assistant'])
def speech_capabilities(user=Depends(current_user)):
    return {'recognition': 'device-native', 'tts': 'device-native', 'languages': ['hi-IN', 'en-IN'],
            'raw_audio_retained': False, 'development_build_required': True,
            'note': 'Transcript correction occurs on device; submit reviewed text to POST /api/v1/chat.'}


@api.delete('/account', tags=['Profile'])
def delete_account(user=Depends(current_user), db=Depends(session)):
    if db.scalar(select(Document.id).where(Document.user_id == user.id, Document.status == 'processing')):
        raise HTTPException(409, 'Wait for document processing to finish before deleting your account')
    keys = [read(p)['storage_key'] for p in db.scalars(select(Page).where(Page.user_id == user.id))]
    db.delete(user)
    db.commit()
    for key in keys:
        remove(key)
    return {'message': 'Account and patient records deleted. Encrypted backups follow retention policy.'}


app.include_router(api)
