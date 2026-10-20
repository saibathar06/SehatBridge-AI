import base64
import io
from pathlib import Path
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from fastapi import HTTPException
from .config import settings
from .models import uid
from .security import seal, unseal

Image.MAX_IMAGE_PIXELS = 24000000


def storage_root():
    path = Path(settings().storage_path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_bytes(raw, user_id):
    key = uid()
    (storage_root() / key).write_text(seal(base64.b64encode(raw).decode(), f'file:{user_id}:{key}'))
    return key


def get_bytes(key, user_id):
    # Keys are generated UUIDs, never client-controlled paths.
    import uuid
    if str(uuid.UUID(key)) != key:
        raise ValueError('Invalid storage key')
    encoded = (storage_root() / key).read_text()
    return base64.b64decode(unseal(encoded, f'file:{user_id}:{key}'))


def remove(key):
    import uuid
    if str(uuid.UUID(key)) != key:
        raise ValueError('Invalid storage key')
    (storage_root() / key).unlink(missing_ok=True)


def split_upload(raw):
    if len(raw) > settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, 'Document exceeds file size limit')
    try:
        if raw.startswith(b'%PDF-'):
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted or not reader.pages or len(reader.pages) > settings().max_pages:
                raise ValueError()
            result = []
            for page in reader.pages:
                writer, output = PdfWriter(), io.BytesIO()
                writer.add_page(page)
                writer.write(output)
                result.append((output.getvalue(), 'application/pdf'))
            return result
        if not (raw.startswith(b'\xff\xd8\xff') or raw.startswith(b'\x89PNG\r\n\x1a\n')):
            raise ValueError()
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError()
            cleaned = ImageOps.exif_transpose(image).convert('RGB')
            output = io.BytesIO()
            cleaned.save(output, format='JPEG', quality=90)  # strip metadata
            return [(output.getvalue(), 'image/jpeg')]
    except Exception:
        raise HTTPException(422, 'Invalid, encrypted, oversized or unsupported document. Use readable PDF, JPEG or PNG.')
