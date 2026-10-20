"""Fail-closed provider boundary. A licensed, reviewed drug reference adapter can replace this."""


def medicine_information(language):
    if language == 'hi':
        return 'दवा और उसकी सही ताकत की पुष्टि करें। अभी कोई सत्यापित दवा-सुरक्षा स्रोत जुड़ा नहीं है, इसलिए मैं दुष्प्रभाव की सूची नहीं दे सकता। अपने फार्मासिस्ट या चिकित्सक से पूछें। खुद से उपचार न बदलें।'
    return 'Please verify the exact medicine and strength with your pharmacist or clinician. No verified drug-information source is configured, so I cannot provide a supported side-effect list. Do not change treatment on your own.'
