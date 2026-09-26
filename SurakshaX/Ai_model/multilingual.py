import re
import json
import urllib.request
import urllib.parse

class MultilingualSafetyEngine:
    """
    Multilingual AI Ingestion Engine.
    Detects reports submitted in ANY language (Hindi, Assamese, Bengali, Hinglish,
    Spanish, French, Arabic, etc.) and translates/normalizes them to canonical
    safety English for the SurakshaX NLP & Risk engine.
    Works online via translation service and offline via domain safety transliteration lexicon.
    """

    # Offline Vernacular Lexicon for Indian Oilfield Operations
    OFFLINE_VERNACULAR_MAP = [
        # Hindi Devanagari terms
        (r"(?:बिजली|विद्युत|करंट|वायर|तार\s*खुला|तार)", "electrical energy live wire exposed conductor"),
        (r"(?:पंप\s*रखरखाव|पंप)", "mud pump maintenance equipment"),
        (r"(?:गैस\s*रिसाव|गैस\s*लीक|गैस|रिसाव|लीक|आग|शोला|धुआं|बदबू|कच्चा\s*तेल)", "hydrocarbon gas vapor release fire risk"),
        (r"(?:ऊंचाई|गिरना|मचान|सीढ़ी|बिना\s*हार्नेस|हार्नेस)", "working at height fall hazard without harness lifeline"),
        (r"(?:पाइप\s*फटना|पाइप|प्रेशर|दबाव|हाइड्रोलिक)", "high pressure hydraulic fluid rupture jet stream"),
        (r"(?:गंभीर\s*खतरा|खतरा|हादसा|चोट|दुर्घटना|गंभीर)", "severe critical SIF danger hazard line of fire"),
        (r"(?:कोई\s*खतरा\s*नहीं|सब\s*सुरक्षित|सामान्य|ठीक)", "no leak observed routine inspection normal all safe"),
        
        # Hinglish & Latin script vernacular terms
        (r"\b(?:bijli|vidyut|karan|current|tar\s+khula|live\s+wire|switchgear)\b", "electrical energy live wire exposed conductor"),
        (r"\b(?:gas\s+risav|gas\s+leak|aag|shola|badbu|h2s|crude\s+leak|flange\s+leak)\b", "hydrocarbon gas vapor release fire risk"),
        (r"\b(?:unchai|unchi\s+jagah|girna|gir\s+gaya|scaffold\s+bina|bina\s+harness|harness\s+nahi|lifeline\s+nahi)\b", "working at height fall hazard without harness lifeline"),
        (r"\b(?:pipe\s+phat|hose\s+phat|burst|pressure\s+bahut|hydraulic\s+leak|dhar)\b", "high pressure hydraulic fluid rupture jet stream"),
        (r"\b(?:isolation\s+nahi|loto\s+nahi|band\s+nahi|padlock\s+nahi|isolation\s+incomplete)\b", "isolation was not completed LOTO missing barrier bypassed"),
        (r"\b(?:worker\s+fas|line\s+of\s+fire|khatre\s+me|khatra|aadmi\s+niche|unprotected)\b", "worker in direct line of fire exposed to hazard"),
        (r"\b(?:koi\s+leak\s+nahi|koi\s+khatra\s+nahi|sab\s+theek|sab\s+safe|inspection\s+normal)\b", "no leak observed routine inspection normal all safe")
    ]

    def __init__(self):
        self._cache = {}

    def translate_online(self, text: str) -> tuple[str, str]:
        """
        Calls the public translation endpoint to automatically translate text from any language into English.
        Returns: (translated_english_text, detected_language_code)
        """
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q={encoded_text}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            translated_chunks = []
            if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                for chunk in data[0]:
                    if chunk and isinstance(chunk, list) and len(chunk) > 0 and chunk[0]:
                        translated_chunks.append(chunk[0])
            
            translated_text = "".join(translated_chunks).strip()
            detected_lang = data[2] if len(data) > 2 and data[2] else "auto"
            return translated_text, detected_lang

    def process_multilingual_report(self, text: str) -> dict:
        """
        Main entry point for multilingual report processing.
        Returns canonical English text, detected language, and translation metadata.
        """
        raw = text.strip()
        if not raw:
            return {"original_text": "", "canonical_text": "", "detected_lang": "EN", "is_translated": False}

        if raw in self._cache:
            return self._cache[raw]

        # Check script
        has_devanagari = any(0x0900 <= ord(char) <= 0x097F for char in raw)
        has_bengali_assamese = any(0x0980 <= ord(char) <= 0x09FF for char in raw)
        has_non_ascii = any(ord(char) > 127 for char in raw)

        # Offline Vernacular check for Hindi / Hinglish / Regional Indian oilfield terms
        text_lower = raw.lower()
        normalized_words = text_lower
        matched_vernacular = False

        for pattern, replacement in self.OFFLINE_VERNACULAR_MAP:
            if re.search(pattern, normalized_words):
                matched_vernacular = True
                normalized_words = re.sub(pattern, replacement, normalized_words)

        # Fast-path: If pure ASCII and no vernacular/Hinglish terms matched, return immediately without network call
        if not has_non_ascii and not matched_vernacular:
            res = {
                "original_text": raw,
                "canonical_text": raw,
                "detected_lang": "EN",
                "is_translated": False,
                "method": "Native English"
            }
            self._cache[raw] = res
            return res

        # Attempt online translation only when non-ASCII or vernacular tokens are present
        try:
            translated, lang_code = self.translate_online(raw)
            if translated and translated.lower() != raw.lower():
                res = {
                    "original_text": raw,
                    "canonical_text": translated,
                    "detected_lang": lang_code.upper() if lang_code != "auto" else ("HI" if has_devanagari else "EN"),
                    "is_translated": True,
                    "method": "Universal AI Neural Translation"
                }
                self._cache[raw] = res
                return res
        except Exception:
            pass

        if matched_vernacular or has_devanagari or has_bengali_assamese:
            lang = "HI" if has_devanagari else ("AS" if has_bengali_assamese else "Vernacular / Hinglish")
            res = {
                "original_text": raw,
                "canonical_text": normalized_words,
                "detected_lang": lang,
                "is_translated": True,
                "method": "Offline Safety Vernacular Lexicon"
            }
            self._cache[raw] = res
            return res

        res = {
            "original_text": raw,
            "canonical_text": raw,
            "detected_lang": "EN",
            "is_translated": False,
            "method": "Native English"
        }
        self._cache[raw] = res
        return res
