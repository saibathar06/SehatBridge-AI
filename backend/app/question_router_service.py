import re
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from .gemini_service import gemini
from .medicine_information_service import medicine_information


def answer_question(question, language, context, document_id=None):
    q = question.lower()
    hi = language == 'hi'
    if any(term in q for term in ('chest pain', 'cannot breathe', 'severe bleeding', 'unconscious', 'सीने में दर्द', 'सांस नहीं', 'सांस लेने में तकलीफ', 'बेहोश')):
        return {'answer': 'तुरंत स्थानीय आपातकालीन चिकित्सा सहायता लें। इस चैट के जवाब का इंतज़ार न करें।' if hi else
                'Seek urgent professional medical help now through your local emergency service. Do not wait for this chat.', 'route': 'urgent', 'sources': []}
    if any(term in q for term in ('side effect', 'side-effect', 'headache', 'interaction', 'safe to', 'दुष्प्रभाव', 'साइड इफेक्ट', 'सिरदर्द', 'सुरक्षित', 'दोगुनी', 'stop ', 'double ', 'बंद कर', 'dose change')):
        return {'answer': medicine_information(language), 'route': 'medicine_safety', 'sources': []}
    plans = context['plans']
    if document_id:
        plans = [p for p in plans if p['document_id'] == document_id]
        if not plans:
            raise HTTPException(404, 'Confirmed document not found')
    routine_medicine = any(term in q for term in ('today', 'medicine', 'dose', 'taken', 'सुबह', 'दवाई', 'दवा', 'आज', 'ली थी'))
    routine_follow = any(term in q for term in ('test', 'follow', 'visit', 'जांच', 'जाँच', 'टेस्ट', 'फॉलो', 'नेक्स्ट'))
    explanation = any(term in q for term in ('explain', 'summary', 'report', 'discharge', 'समझा', 'रिपोर्ट', 'बताया', 'सावधान'))
    sources = []
    if (routine_medicine or routine_follow) and not explanation:
        parts = []
        if routine_medicine:
            ds = context['doses']
            if document_id:
                allowed = {p['id'] for p in plans}
                ds = [d for d in ds if d['treatment_id'] in allowed]
            if ds:
                lines = []
                for d in ds:
                    m = d['medicine']
                    clock = datetime.fromtimestamp(d['due_at'], ZoneInfo(d['timezone'])).strftime('%H:%M')
                    status = {'taken': 'ले ली', 'skipped': 'छोड़ी', 'missed': 'छूट गई', 'upcoming': 'आगामी'}.get(d['status'], d['status']) if hi else d['status']
                    lines.append(f"{m['name']} — {m.get('dose', '')} {m.get('dose_unit', '')}, {clock} ({d['timezone']}); {status}")
                    sources.append(m['source'])
                parts.append(('आज की पुष्टि की गई समय-सारणी:\n' if hi else "Today's confirmed schedule:\n") + '\n'.join(lines))
            else:
                parts.append('आज के लिए कोई पुष्टि की गई दवा की समय-सारणी नहीं मिली।' if hi else 'No confirmed scheduled doses were found for today.')
        if routine_follow:
            upcoming = []
            today = datetime.now(ZoneInfo(context['profile']['timezone'])).date().isoformat()
            undated = []
            for p in plans:
                ex = p['extraction']
                for item in ex['tests'] + ex['follow_ups']:
                    if not item.get('date'):
                        undated.append(item)
                    elif item['date'] >= today:
                        upcoming.append(item)
            upcoming.sort(key=lambda f: f['date'])
            if upcoming:
                next_item = upcoming[0]
                parts.append(('अगली जांच / मुलाकात: ' if hi else 'Next test / follow-up: ') + next_item['name'] + ' — ' + next_item['date'])
                sources.append(next_item['source'])
            else:
                parts.append('अगली जांच या मुलाकात की पक्की तारीख उपलब्ध नहीं है। चिकित्सक से पुष्टि करें।' if hi else 'No dated upcoming test or follow-up is recorded. Please confirm with your clinician.')
            for item in undated:
                parts.append(f"{item['name']}: " + ('तारीख अस्पष्ट है; पुष्टि करें।' if hi else 'Date is unclear; please verify.'))
                sources.append(item['source'])
        return {'answer': '\n\n'.join(parts), 'route': 'structured_records', 'sources': sources}
    if not plans:
        return {'answer': 'पहले अपना दस्तावेज़ अपलोड करके उपचार की पुष्टि करें। मेरे पास अभी पुष्टि किए गए रिकॉर्ड नहीं हैं।' if hi else
                'Upload a document and confirm the reviewed plan first. I do not have confirmed records to explain yet.', 'route': 'no_context', 'sources': []}
    for p in plans:
        for key in ('medicines', 'tests', 'follow_ups', 'instructions'):
            sources += [v['source'] for v in p['extraction'][key]]
    return {'answer': gemini.explain(question, language, plans), 'route': 'document_explanation', 'sources': sources[:20]}
