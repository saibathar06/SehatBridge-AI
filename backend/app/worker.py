"""Durable PostgreSQL work queue. Run independently: python -m app.worker."""
import time
from sqlalchemy import select, or_, and_
from fastapi import HTTPException
from .db import SessionLocal
from .models import Document, Page, Analysis, now
from .security import read, put, audit
from .storage import get_bytes
from .gemini_service import gemini
from .schemas import Extraction
from .config import settings
from .notifications import deliver_due


def combine_batches(batches, page_count):
    first = batches[0].model_dump(mode='json')
    for batch in batches[1:]:
        data = batch.model_dump(mode='json')
        first['summary'] = (first['summary'] + '\n' + data['summary'])[:6000]
        for key in ('medicines', 'follow_ups', 'tests', 'instructions', 'review_flags'):
            first[key] += data[key]
    if len(batches) > 1:
        first['review_flags'].append('Multi-batch extraction: verify cross-page continuity and conflicting instructions.')
    # Potential duplicate/cross-page conflicting medicines must never silently activate twice.
    names = {}
    for med in first['medicines']:
        name = (med['name'] or '').strip().lower()
        names.setdefault(name, []).append(med)
    for group in names.values():
        if len(group) > 1:
            for med in group:
                med['clarification_required'] = True
                med['review_flags'].append('Repeated or conflicting medicine across pages: verify together.')
    return Extraction.model_validate(first).validate_sources(page_count)


def process_one():
    with SessionLocal() as db:
        doc = db.scalar(select(Document).where(or_(Document.status == 'queued',
            and_(Document.status == 'processing', Document.lease_until < now())))
            .with_for_update(skip_locked=True).limit(1))
        if not doc:
            return False
        if doc.attempts >= 3:
            doc.status = 'error'
            put(doc, {**read(doc), 'error': 'Processing retry limit reached. Please retry manually.'})
            db.commit()
            return True
        doc.status = 'processing'
        doc.attempts += 1
        # Lease exceeds bounded maximum call duration for the entire document.
        doc.lease_until = int(now()) + (settings().max_pages // settings().extraction_batch_pages + 1) * settings().ai_timeout_seconds * 3 + 120
        db.commit()
        try:
            pages = db.scalars(select(Page).where(Page.document_id == doc.id).order_by(Page.position)).all()
            payload = [(p.position, get_bytes(read(p)['storage_key'], p.user_id), read(p)['mime']) for p in pages]
            size = settings().extraction_batch_pages
            batches = [gemini.extract(payload[i:i + size]) for i in range(0, len(payload), size)]
            extraction = combine_batches(batches, len(pages))
            existing = db.scalar(select(Analysis).where(Analysis.document_id == doc.id))
            if not existing:
                existing = Analysis(user_id=doc.user_id, document_id=doc.id)
                db.add(existing)
            put(existing, extraction.model_dump(mode='json'))
            doc.status = 'review'
            put(doc, {**read(doc), 'error': None})
            audit(db, doc.user_id, 'extraction_ready', doc.id)
        except Exception as error:
            db.rollback()
            doc = db.get(Document, doc.id)
            if doc:
                doc.status = 'error'
                public_error = error.detail if isinstance(error, HTTPException) else 'Processing failed validation or timed out. Review the source and retry.'
                put(doc, {**read(doc), 'error': public_error})
        db.commit()
        return True


def main():
    while True:
        try:
            busy = process_one()
            with SessionLocal() as db:
                deliver_due(db)
        except Exception:
            busy = False  # worker recovers; supervisor should monitor readiness
        if not busy:
            time.sleep(5)


if __name__ == '__main__':
    main()
