"""Lightweight safety layer: emergency triage keywords and Indian helplines.

This is a keyword guardrail, not a classifier. It only *adds* a warning banner and
helpline list on top of the model reply - it never suppresses the model's own caution.
"""

from __future__ import annotations

import re

# GenAI Generated code - Start

#: Official Indian helpline numbers (verify periodically - numbers do change).
HELPLINES: list[dict[str, str]] = [
    {
        "id": "emergency",
        "name": "National Emergency Number",
        "number": "112",
        "note": "Police, fire, ambulance - all India",
        "urgent": "true",
    },
    {
        "id": "ambulance",
        "name": "Ambulance",
        "number": "108",
        "note": "Free emergency ambulance in most states",
        "urgent": "true",
    },
    {
        "id": "health",
        "name": "National Health Helpline",
        "number": "1075",
        "note": "Ministry of Health advice line",
        "urgent": "false",
    },
    {
        "id": "health-state",
        "name": "State Health Helpline",
        "number": "104",
        "note": "Medical advice and counselling",
        "urgent": "false",
    },
    {
        "id": "telemanas",
        "name": "Tele-MANAS Mental Health",
        "number": "14416",
        "note": "24x7 mental health support, many languages",
        "urgent": "false",
    },
    {
        "id": "kiran",
        "name": "KIRAN Mental Health",
        "number": "1800-599-0019",
        "note": "24x7 toll free counselling",
        "urgent": "false",
    },
    {
        "id": "poison",
        "name": "Poison Control (AIIMS)",
        "number": "1800-116-117",
        "note": "Poisoning, overdose, chemical exposure",
        "urgent": "true",
    },
    {
        "id": "women",
        "name": "Women Helpline",
        "number": "181",
        "note": "Distress and violence support",
        "urgent": "false",
    },
    {
        "id": "child",
        "name": "Childline",
        "number": "1098",
        "note": "Children in need of care",
        "urgent": "false",
    },
    {
        "id": "senior",
        "name": "Elderline",
        "number": "14567",
        "note": "Senior citizen helpline",
        "urgent": "false",
    },
]

# --- emergency keyword sets -------------------------------------------------
# English plus common transliterations and native-script terms. Kept broad on
# purpose: a false positive only shows an extra "call 112" banner.

_RED_FLAGS = [
    # cardiac / respiratory
    r"chest pain", r"chest tightness", r"heart attack", r"cardiac arrest",
    r"can(?:'|no)?t breathe", r"cannot breathe", r"not breathing", r"breathless",
    r"shortness of breath", r"gasping", r"choking", r"turning blue",
    # neuro
    r"unconscious", r"unresponsive", r"fainted", r"seizure", r"convulsion", r"fits",
    r"stroke", r"slurred speech", r"face droop", r"paralysis", r"sudden numbness",
    r"severe head injury", r"head injury", r"neck injury",
    # bleeding / trauma
    r"heavy bleeding", r"severe bleeding", r"bleeding a lot", r"blood loss",
    r"vomiting blood", r"coughing blood", r"blood in stool", r"deep cut",
    r"accident", r"fracture", r"broken bone", r"major burn", r"electric shock",
    r"drowning", r"snake bite", r"dog bite", r"scorpion sting",
    # poisoning
    r"poison", r"overdose", r"swallowed", r"pesticide", r"kerosene", r"phenyl",
    # obstetric / paediatric
    r"labour pain", r"labor pain", r"water broke", r"baby not moving",
    r"miscarriage", r"newborn fever", r"infant fever", r"baby not feeding",
    # systemic
    r"very high fever", r"fever 10[4-9]", r"severe dehydration", r"cannot stand",
    r"collapsed", r"blood sugar very (?:high|low)", r"anaphyla", r"swollen tongue",
    r"swollen throat", r"severe allergic",
    # self harm
    r"suicide", r"suicidal", r"kill myself", r"end my life", r"self harm",
    r"harm myself", r"want to die",
    # transliterated Hindi / regional
    r"seene mein dard", r"saans nahi", r"behosh", r"bahut khoon", r"zeher",
    r"saap ne kata", r"dam ghut",
]

_NATIVE_RED_FLAGS = [
    # Hindi / Marathi (Devanagari)
    "सीने में दर्द", "छाती में दर्द", "सांस नहीं", "सांस लेने में", "बेहोश",
    "दौरा", "बहुत खून", "खून बह", "ज़हर", "जहर", "सांप ने काटा", "आत्महत्या",
    "छातीत दुखणे", "श्वास घेता येत नाही", "शुद्ध हरपली", "विष", "आत्महत्या",
    # Telugu
    "ఛాతీ నొప్పి", "ఊపిరి ఆడటం లేదు", "శ్వాస తీసుకోలేక", "స్పృహ లేదు",
    "రక్తస్రావం", "విషం", "పాము కాటు", "ఆత్మహత్య",
    # Tamil
    "நெஞ்சு வலி", "மூச்சு விட முடியவில்லை", "மயக்கம்", "அதிக ரத்தப்போக்கு",
    "விஷம்", "பாம்பு கடி", "தற்கொலை",
    # Bengali
    "বুকে ব্যথা", "শ্বাস নিতে", "অজ্ঞান", "প্রচুর রক্ত", "বিষ", "সাপে কাটা",
    "আত্মহত্যা",
]

_RED_FLAG_RE = re.compile("|".join(_RED_FLAGS), re.IGNORECASE)

_SELF_HARM_RE = re.compile(
    r"suicide|suicidal|kill myself|end my life|self harm|harm myself|want to die"
    r"|आत्महत्या|ఆత్మహత్య|தற்கொலை|আত্মহত্যা",
    re.IGNORECASE,
)

_ESCALATION_RE = re.compile(
    r"didn'?t help|did not help|not working|no relief|still (?:have|having|same)"
    r"|getting worse|worse now|tried everything|remedies failed|koi fayda nahi"
    r"|aaram nahi|फायदा नहीं|आराम नहीं|ఉపయోగం లేదు|తగ్గలేదు|குணமாகவில்லை"
    r"|পার্থক্য হয়নি|কাজ হচ্ছে না",
    re.IGNORECASE,
)

_EMERGENCY_BANNER = {
    "en": "This may need emergency care. Please call **112** (emergency) or **108** (ambulance) now, or go to the nearest hospital. Do not wait for home remedies.",
    "hi": "यह आपातकालीन स्थिति हो सकती है। कृपया अभी **112** या **108** पर कॉल करें, या नज़दीकी अस्पताल जाएँ। घरेलू उपाय का इंतज़ार न करें।",
    "ta": "இது அவசர சிகிச்சை தேவைப்படும் நிலையாக இருக்கலாம். உடனே **112** அல்லது **108** ஐ அழைக்கவும், அல்லது அருகிலுள்ள மருத்துவமனைக்குச் செல்லவும்.",
    "te": "ఇది అత్యవసర చికిత్స అవసరమైన పరిస్థితి కావచ్చు. వెంటనే **112** లేదా **108** కు కాల్ చేయండి, లేదా దగ్గరి ఆసుపత్రికి వెళ్లండి.",
    "bn": "এটি জরুরি চিকিৎসার প্রয়োজন হতে পারে। এখনই **112** বা **108** নম্বরে ফোন করুন, বা নিকটতম হাসপাতালে যান।",
    "mr": "ही आपत्कालीन स्थिती असू शकते. कृपया आत्ताच **112** किंवा **108** वर कॉल करा, किंवा जवळच्या रुग्णालयात जा.",
}

_SELF_HARM_BANNER = {
    "en": "You deserve support right now. Please call **112**, or **Tele-MANAS 14416** / **KIRAN 1800-599-0019** to talk to a trained counsellor. If you are in immediate danger, reach the nearest emergency room and stay with someone you trust.",
    "hi": "आप इस समय सहायता के हक़दार हैं। कृपया **112**, या **टेली-मानस 14416** / **किरण 1800-599-0019** पर बात करें। तुरंत ख़तरा हो तो नज़दीकी अस्पताल जाएँ और किसी भरोसेमंद व्यक्ति के साथ रहें।",
    "ta": "இப்போது உங்களுக்கு உதவி தேவை. **112**, அல்லது **Tele-MANAS 14416** / **KIRAN 1800-599-0019** ஐ அழைக்கவும். உடனடி ஆபத்து இருந்தால் அருகிலுள்ள மருத்துவமனைக்குச் செல்லவும்.",
    "te": "ఇప్పుడు మీకు సహాయం అవసరం. **112**, లేదా **Tele-MANAS 14416** / **KIRAN 1800-599-0019** కు కాల్ చేయండి. తక్షణ ప్రమాదం ఉంటే దగ్గరి ఆసుపత్రికి వెళ్లండి.",
    "bn": "এই মুহূর্তে আপনার সহায়তা প্রয়োজন। **112**, বা **Tele-MANAS 14416** / **KIRAN 1800-599-0019** নম্বরে কথা বলুন। তাৎক্ষণিক বিপদ হলে নিকটতম হাসপাতালে যান।",
    "mr": "या क्षणी तुम्हाला मदतीची गरज आहे. **112**, किंवा **Tele-MANAS 14416** / **KIRAN 1800-599-0019** वर संपर्क करा. तातडीचा धोका असल्यास जवळच्या रुग्णालयात जा.",
}


def detect_emergency(text: str, language: str = "en") -> dict | None:
    """Return a banner payload when the message looks urgent, else ``None``."""
    if not text:
        return None
    lowered = text.lower()
    self_harm = bool(_SELF_HARM_RE.search(text))
    hit = self_harm or bool(_RED_FLAG_RE.search(lowered)) or any(
        term in text for term in _NATIVE_RED_FLAGS
    )
    if not hit:
        return None
    kind = "self_harm" if self_harm else "medical"
    table = _SELF_HARM_BANNER if self_harm else _EMERGENCY_BANNER
    numbers = (
        ["112", "14416", "1800-599-0019"] if self_harm else ["112", "108", "1075"]
    )
    return {
        "kind": kind,
        "message": table.get(language, table["en"]),
        "numbers": numbers,
    }


def detect_escalation(text: str) -> bool:
    """True when the user signals that remedies are not working."""
    return bool(text) and bool(_ESCALATION_RE.search(text))
# GenAI Generated code - End
