"""Run real Gemini extraction on synthetic fixtures and report field accuracy.
Explicit operator invocation required; this consumes the configured Gemini quota.
"""
import json
from pathlib import Path
from app.gemini_service import gemini
from app.storage import split_upload
from app.worker import combine_batches
from app.config import settings

root = Path(__file__).resolve().parents[1] / 'tests' / 'documents'
manifest = json.loads((root / 'ground_truth.json').read_text())
results, correct, total = [], 0, 0
for case in manifest:
    pages = []
    for file in case['files']:
        for raw, mime in split_upload((root / file).read_bytes()):
            pages.append((len(pages) + 1, raw, mime))
    size = settings().extraction_batch_pages
    ex = combine_batches([gemini.extract(pages[i:i + size]) for i in range(0, len(pages), size)], len(pages))
    med = ex.medicines[0] if ex.medicines else None
    actual = {'medicine_name': med.name if med else None, 'dose': med.dose if med else None,
              'dose_unit': med.dose_unit if med else None, 'frequency': med.frequency if med else None,
              'scheduled_times': med.scheduled_times if med else [], 'duration': med.duration if med else None,
              'clarification_required': med.clarification_required if med else True,
              'follow_up_date': str(ex.follow_ups[0].date) if ex.follow_ups else None,
              'test_date': str(ex.tests[0].date) if ex.tests else None}
    fields = {k: {'expected': v, 'actual': actual[k], 'correct': v == actual[k]} for k, v in case['expected'].items()}
    correct += sum(int(v['correct']) for v in fields.values())
    total += len(fields)
    results.append({'case': case['id'], 'fields': fields})
report = {'model': settings().gemini_model, 'correct_fields': correct, 'total_fields': total,
          'field_accuracy': correct / total if total else 0, 'cases': results,
          'limitation': 'Small synthetic fixtures, not clinical or real handwriting validation.'}
(root / 'evaluation-results.json').write_text(json.dumps(report, indent=2))
print(f'Field accuracy: {correct}/{total}. Full report saved in tests/documents/evaluation-results.json')
