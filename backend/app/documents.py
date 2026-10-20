import json
from typing import Annotated
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request, Response
from sqlalchemy import select, delete
from .db import session
from .models import Document, Page, Analysis, Treatment
from .schemas import ReviewInput
from .security import current_user, owned, read, put, audit, sensitive_limit
from .storage import split_upload, store_bytes, get_bytes, remove
from .config import settings

router = APIRouter(prefix='/documents', tags=['Documents'])


def document_view(db, doc):
    pages = db.scalars(select(Page).where(Page.document_id == doc.id, Page.user_id == doc.user_id).order_by(Page.position)).all()
    return {'id': doc.id, 'status': doc.status, **read(doc), 'pages': [
        {'id': p.id, 'position': p.position, 'mime': read(p)['mime']} for p in pages]}


@router.post('', status_code=201)
def upload(request: Request, files: Annotated[list[UploadFile], File()],
           document_type: Annotated[str, Form()], ai_consent: Annotated[bool, Form()],
           user=Depends(current_user), db=Depends(session)):
    sensitive_limit(request, user.id, 'upload', 5)
    if not ai_consent:
        raise HTTPException(422, 'Consent to third-party AI processing is required')
    if document_type not in ('prescription', 'discharge', 'laboratory', 'other'):
        raise HTTPException(422, 'Unknown document type')
    if not files or len(files) > settings().max_pages:
        raise HTTPException(422, 'Too many files')
    # Validate the complete group before writing any private storage objects.
    pages, total = [], 0
    for file in files:
        raw = file.file.read(settings().max_upload_mb * 1024 * 1024 + 1)
        total += len(raw)
        if total > settings().max_upload_mb * 1024 * 1024:
            raise HTTPException(413, 'Upload group exceeds total size limit')
        pages.extend(split_upload(raw))
        if len(pages) > settings().max_pages:
            raise HTTPException(422, 'Document exceeds page limit')
    from .models import now
    doc = put(Document(user_id=user.id), {'document_type': document_type, 'created_at': now(), 'error': None, 'ai_consent': True})
    db.add(doc)
    db.flush()
    keys = []
    try:
        for position, (raw, mime) in enumerate(pages, 1):
            key = store_bytes(raw, user.id)
            keys.append(key)
            db.add(put(Page(user_id=user.id, document_id=doc.id, position=position), {'storage_key': key, 'mime': mime}))
        audit(db, user.id, 'document_uploaded', doc.id)
        db.commit()
    except Exception:
        for key in keys:
            remove(key)
        raise
    return document_view(db, doc)


@router.get('')
def documents(user=Depends(current_user), db=Depends(session)):
    return [document_view(db, d) for d in db.scalars(select(Document).where(Document.user_id == user.id))]


@router.get('/{document_id}')
def status(document_id: str, user=Depends(current_user), db=Depends(session)):
    return document_view(db, owned(db, Document, document_id, user.id))


@router.get('/{document_id}/pages/{page_id}')
def page(document_id: str, page_id: str, preview: bool = False, user=Depends(current_user), db=Depends(session)):
    owned(db, Document, document_id, user.id)
    p = owned(db, Page, page_id, user.id)
    if p.document_id != document_id:
        raise HTTPException(404, 'Page not found')
    data = read(p)
    raw, mime = get_bytes(data['storage_key'], user.id), data['mime']
    if preview and mime == 'application/pdf':
        import pymupdf
        with pymupdf.open(stream=raw, filetype='pdf') as pdf:
            page = pdf[0]
            scale = min(1.5, 1600 / max(page.rect.width, page.rect.height))
            raw, mime = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png'), 'image/png'
    return Response(raw, media_type=mime,
                    headers={'Cache-Control': 'no-store', 'Content-Disposition': 'inline', 'X-Content-Type-Options': 'nosniff'})


@router.post('/{document_id}/retry')
def retry(document_id: str, request: Request, user=Depends(current_user), db=Depends(session)):
    sensitive_limit(request, user.id, 'extraction', 3)
    d = owned(db, Document, document_id, user.id, lock=True)
    if d.status != 'error':
        raise HTTPException(409, 'Only failed documents can be retried')
    d.status, d.attempts, d.lease_until = 'queued', 0, 0
    put(d, {**read(d), 'error': None})
    return {'status': d.status}


@router.get('/{document_id}/analysis')
def analysis(document_id: str, user=Depends(current_user), db=Depends(session)):
    owned(db, Document, document_id, user.id)
    a = db.scalar(select(Analysis).where(Analysis.document_id == document_id, Analysis.user_id == user.id))
    if not a:
        raise HTTPException(409, 'Extraction is not ready yet')
    return {'revision': a.revision, 'extraction': read(a)}


@router.put('/{document_id}/analysis')
def edit_analysis(document_id: str, body: ReviewInput, user=Depends(current_user), db=Depends(session)):
    d = owned(db, Document, document_id, user.id, lock=True)
    if db.scalar(select(Treatment.id).where(Treatment.document_id == document_id)):
        raise HTTPException(409, 'Use treatment schedule reconciliation for an already confirmed plan')
    a = db.scalar(select(Analysis).where(Analysis.document_id == document_id, Analysis.user_id == user.id).with_for_update())
    if not a or a.revision != body.revision:
        raise HTTPException(409, 'Draft changed. Reload before saving.')
    count = len(db.scalars(select(Page.id).where(Page.document_id == d.id)).all())
    try:
        body.extraction.validate_sources(count)
    except ValueError as e:
        raise HTTPException(422, str(e))
    put(a, body.extraction.model_dump(mode='json'))
    a.revision += 1
    audit(db, user.id, 'draft_corrected', d.id)
    return {'revision': a.revision, 'extraction': read(a)}


@router.delete('/{document_id}')
def delete_document(document_id: str, user=Depends(current_user), db=Depends(session)):
    d = owned(db, Document, document_id, user.id, lock=True)
    if d.status == 'processing':
        raise HTTPException(409, 'Wait until processing finishes before deleting')
    pages = db.scalars(select(Page).where(Page.document_id == d.id)).all()
    keys = [read(p)['storage_key'] for p in pages]
    db.delete(d)  # FK cascades include schedules/doses. Device reconciliation removes pending reminders.
    audit(db, user.id, 'document_deleted', d.id)
    db.commit()
    for key in keys:
        remove(key)
    return {'message': 'Document and associated treatment deleted. Reconcile device reminders.'}
