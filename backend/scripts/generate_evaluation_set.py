"""Generate synthetic visual fixtures and independently specified ground truth.
These are SOFTWARE tests; synthetic handwriting is not clinical handwriting validation.
"""
import io
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pypdf import PdfReader, PdfWriter

root = Path(__file__).resolve().parents[1] / 'tests' / 'documents'
root.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype('DejaVuSans.ttf', 28) if Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').exists() else ImageFont.load_default(size=28)


def page(lines):
    image = Image.new('RGB', (1000, 1300), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((55, 45), 'SYNTHETIC — NOT FOR CLINICAL USE', fill='black', font=font)
    for i, line in enumerate(lines):
        draw.text((55, 140 + i * 65), line, fill='black', font=font)
    return image


cases = [
    ('printed', ['Prescription — Synthetic Patient', 'SYNTHETIC MEDICINE A 10 test units', 'Dose: 1 test tablet once daily at 08:00', 'Duration: 3 days'],
     {'medicine_name': 'SYNTHETIC MEDICINE A', 'dose': '1', 'dose_unit': 'test tablet', 'frequency': 'once daily', 'scheduled_times': ['08:00'], 'duration': '3 days', 'clarification_required': False}),
    ('missing_details', ['Prescription — Synthetic Patient', 'SYNTHETIC MEDICINE B', 'Dose: [not documented]', 'Duration: [not documented]'],
     {'medicine_name': 'SYNTHETIC MEDICINE B', 'dose': None, 'duration': None, 'clarification_required': True}),
    ('conflicting', ['Prescription — Synthetic Patient', 'SYNTHETIC MEDICINE C 10 test units', 'Take 1 test tablet once daily', 'Conflicting note: take 2 test tablets twice daily'],
     {'medicine_name': 'SYNTHETIC MEDICINE C', 'clarification_required': True}),
    ('similar_digits', ['Prescription — Synthetic Patient', 'SYNTHETIC MEDICINE D', 'Strength: 10 or 70? [ambiguous]', 'Dose: 1 or 7? [ambiguous]'],
     {'medicine_name': 'SYNTHETIC MEDICINE D', 'clarification_required': True}),
]
manifest = []
for name, lines, truth in cases:
    image = page(lines)
    image.save(root / f'{name}.png')
    manifest.append({'id': name, 'files': [f'{name}.png'], 'expected': truth})
    if name == 'printed':
        image.rotate(90, expand=True).filter(ImageFilter.GaussianBlur(3)).save(root / 'rotated_blurry.png')
        manifest.append({'id': 'rotated_blurry', 'files': ['rotated_blurry.png'], 'expected': {'clarification_required': True}})

discharge = [page(['Discharge summary — page 1 of 2', 'Synthetic Patient', 'Care instruction: keep the synthetic dressing dry.']),
             page(['Discharge summary — page 2 of 2', 'Follow-up: Synthetic Clinic on 2099-01-01', 'Investigation: Synthetic test on 2099-01-02'])]
discharge[0].save(root / 'discharge.pdf', save_all=True, append_images=discharge[1:])
for i, image in enumerate(discharge, 1):
    image.save(root / f'photo-page-{i}.jpg', quality=80)
truth = {'follow_up_date': '2099-01-01', 'test_date': '2099-01-02'}
manifest += [{'id': 'multipage_pdf', 'files': ['discharge.pdf'], 'expected': truth},
             {'id': 'multiple_photos', 'files': ['photo-page-1.jpg', 'photo-page-2.jpg'], 'expected': truth}]
# Deliberately unreadable pen-like strokes, an illegibility hard negative (not a real handwriting sample).
image = page(['Handwriting illegibility hard negative — synthetic'])
draw = ImageDraw.Draw(image)
for y in (330, 450, 570):
    draw.line([(90 + x * 30, y + ((x * 17) % 43)) for x in range(25)], fill='#244060', width=5)
image.save(root / 'illegible_strokes.png')
manifest.append({'id': 'illegible_strokes', 'files': ['illegible_strokes.png'], 'expected': {'medicine_name': None, 'clarification_required': True}})
(root / 'ground_truth.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Generated {len(manifest)} synthetic evaluation cases; real handwriting validation remains required.')
