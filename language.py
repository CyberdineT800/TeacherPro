import json
import os
from typing import Dict, Any

class LanguageManager:
    def __init__(self):
        self.locales_dir = "locales"
        self.languages = {
            'uz': 'O\'zbek',
            'ru': 'Русский',
            'en': 'English'
        }
        self.translations = {}
        self.load_translations()
    
    def load_translations(self):
        """Load all translation files"""
        for lang_code in self.languages.keys():
            file_path = os.path.join(self.locales_dir, f"{lang_code}.json")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
            except FileNotFoundError:
                print(f"Warning: Translation file for {lang_code} not found")
                self.translations[lang_code] = {}
    
    def get(self, key: str, lang_code: str = 'uz', default: str = None) -> str:
        """Get translation for a key"""
        if lang_code not in self.translations:
            lang_code = 'uz'  # Fallback to Uzbek
        
        return self.translations[lang_code].get(key, default or key)
    
    def get_language_name(self, lang_code: str) -> str:
        """Get language name by code"""
        return self.languages.get(lang_code, 'O\'zbek')
    
    def get_available_languages(self) -> Dict[str, str]:
        """Get available languages"""
        return self.languages
    
    def save_translation(self, lang_code: str, key: str, value: str) -> bool:
        """Save or update a translation"""
        if lang_code not in self.languages:
            return False
        
        if lang_code not in self.translations:
            self.translations[lang_code] = {}
        
        self.translations[lang_code][key] = value
        return self._save_to_file(lang_code)
    
    def delete_translation(self, lang_code: str, key: str) -> bool:
        """Delete a translation"""
        if lang_code not in self.translations or key not in self.translations[lang_code]:
            return False
        
        del self.translations[lang_code][key]
        return self._save_to_file(lang_code)
    
    def _save_to_file(self, lang_code: str) -> bool:
        """Save translations to file"""
        try:
            file_path = os.path.join(self.locales_dir, f"{lang_code}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.translations[lang_code], f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"Error saving translation file for {lang_code}: {e}")
            return False
    
    def get_all_translations(self, lang_code: str) -> Dict[str, str]:
        """Get all translations for a language"""
        return self.translations.get(lang_code, {})

# Create global instance
language_manager = LanguageManager()