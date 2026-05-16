"""Multilingual translation manager.

Each gunicorn worker forks its own in-memory copy.  To keep all workers in
sync after an admin edits a translation, the manager checks locale file
modification times every 30 seconds and reloads automatically — no restart
or signal required.
"""
import json
import logging
import os
import time
from typing import Dict

log = logging.getLogger("language")


class LanguageManager:
    # How often (seconds) each worker checks locale file mtimes.
    _CHECK_INTERVAL: float = 30.0

    def __init__(self):
        self.locales_dir = "locales"
        self.languages: Dict[str, str] = {
            'uz': "O'zbek",
            'ru': 'Русский',
            'en': 'English',
        }
        self.translations: Dict[str, Dict[str, str]] = {}

        # mtime tracking
        self._loaded_at: float = 0.0      # time.time() when last loaded
        self._last_check: float = 0.0     # time.monotonic() of last mtime check

        self.load_translations()

    # ── loading ───────────────────────────────────────────────────────────────

    def load_translations(self) -> None:
        """Read all locale JSON files from disk into memory."""
        for lang_code in self.languages:
            path = os.path.join(self.locales_dir, f"{lang_code}.json")
            try:
                with open(path, encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
            except FileNotFoundError:
                log.warning("Translation file missing: %s", path)
                self.translations[lang_code] = {}
            except Exception as e:
                log.error("Failed to load %s: %s", path, e)
                self.translations.setdefault(lang_code, {})

        self._loaded_at = time.time()
        self._last_check = time.monotonic()

    def _check_reload(self) -> None:
        """Reload if any locale file was modified after the last load.

        Runs at most once per _CHECK_INTERVAL seconds (monotonic clock),
        so it adds only a single float comparison on the hot path.
        """
        now = time.monotonic()
        if now - self._last_check < self._CHECK_INTERVAL:
            return
        self._last_check = now

        try:
            for lang_code in self.languages:
                path = os.path.join(self.locales_dir, f"{lang_code}.json")
                if os.path.exists(path) and os.path.getmtime(path) > self._loaded_at:
                    log.info("Locale file changed (%s) — reloading translations", path)
                    self.load_translations()
                    return          # load_translations resets _last_check too
        except Exception as e:
            log.debug("mtime check error: %s", e)

    # ── public API ────────────────────────────────────────────────────────────

    def get(self, key: str, lang_code: str = 'uz', default: str = None) -> str:
        """Return the translation for *key* in *lang_code*.

        Triggers a background mtime check (at most every 30 s) so all
        workers pick up admin changes without a restart.
        """
        self._check_reload()
        if lang_code not in self.translations:
            lang_code = 'uz'
        return self.translations[lang_code].get(key, default if default is not None else key)

    def get_language_name(self, lang_code: str) -> str:
        return self.languages.get(lang_code, "O'zbek")

    def get_available_languages(self) -> Dict[str, str]:
        return self.languages

    def get_all_translations(self, lang_code: str) -> Dict[str, str]:
        return self.translations.get(lang_code, {})

    # ── write helpers (admin only) ────────────────────────────────────────────

    def save_translation(self, lang_code: str, key: str, value: str) -> bool:
        """Update one key in memory and persist to disk."""
        if lang_code not in self.languages:
            return False
        self.translations.setdefault(lang_code, {})[key] = value
        ok = self._save_to_file(lang_code)
        if ok:
            # Bump loaded_at so other workers detect the change within 30 s
            self._loaded_at = time.time()
        return ok

    def delete_translation(self, lang_code: str, key: str) -> bool:
        if lang_code not in self.translations or key not in self.translations[lang_code]:
            return False
        del self.translations[lang_code][key]
        ok = self._save_to_file(lang_code)
        if ok:
            self._loaded_at = time.time()
        return ok

    def _save_to_file(self, lang_code: str) -> bool:
        try:
            path = os.path.join(self.locales_dir, f"{lang_code}.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.translations[lang_code], f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            log.error("Error saving translation file for %s: %s", lang_code, e)
            return False


# Module-level singleton — each worker process has its own copy.
language_manager = LanguageManager()
