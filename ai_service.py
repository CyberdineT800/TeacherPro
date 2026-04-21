"""Gemini-powered AI presentation generator."""
import json
import os
import re
import asyncio
from urllib.parse import quote

import httpx
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MODEL_NAME = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

LANGUAGE_NAMES = {
    'uz': "O'zbek tilida (Uzbek)",
    'ru': 'на русском языке (Russian)',
    'en': 'in English',
}

SYSTEM_PROMPT = """You are an expert teacher creating an interactive educational presentation for school students.

Rules:
- Generate content STRICTLY in the requested language. All text fields (titles, content, questions, options, explanations) must be in that language only.
- Adapt vocabulary, examples, and complexity to the student's grade. In Uzbekistan, students start school at age 7, so grade N corresponds to age N+6.
- Make it INTERACTIVE: include quizzes, true/false, fill-in-the-blank, matching, sequence ordering, and open discussion questions.
- Provide rich, accurate, age-appropriate information on the topic.
- For every slide that benefits from a visual, include an `image_prompt` field in ENGLISH (it is used by an image generator) describing what to show. Do NOT translate image_prompt — keep it English.
- Aim for 12–15 slides total. Mix slide types for variety.
- For quizzes: 4 options, the index of the correct answer (0-3), and a short explanation.
- For matching: 3–5 pairs of [left, right] items.
- For fill-in-the-blank: a sentence with `___` where the blank is, plus the correct answer.
- For sequence: 4–6 ordered items provided already in correct order (they will be shuffled for the student).
- For open_question: a thought-provoking discussion question with 2–3 discussion hints for the teacher.

Return ONLY valid JSON matching this schema (no markdown, no commentary):
{
  "title": "string (presentation title)",
  "subtitle": "string (short hook / age group)",
  "slides": [
    {"type": "title", "title": "...", "subtitle": "...", "image_prompt": "..."},
    {"type": "content", "title": "...", "points": ["...", "..."], "image_prompt": "..."},
    {"type": "other_content", "title": "...", "points": ["...", "..."], "image_prompt": "..."},
    {"type": "other_content", "title": "...", "points": ["...", "..."], "image_prompt": "..."},
    {"type": "image_focus", "title": "...", "caption": "...", "image_prompt": "..."},
    {"type": "quiz", "question": "...", "options": ["A", "B", "C", "D"], "correct": 0, "explanation": "..."},
    {"type": "true_false", "statement": "...", "is_true": true, "explanation": "..."},
    {"type": "fill_blank", "title": "...", "sentence": "Sun is a ___.", "answer": "star", "hint": "..."},
    {"type": "match", "title": "...", "pairs": [["left1","right1"], ["left2","right2"]]},
    {"type": "sequence", "title": "...", "items": ["step1","step2","step3","step4"], "explanation": "..."},
    {"type": "open_question", "question": "...", "hints": ["hint1","hint2","hint3"]},
    {"type": "summary", "title": "...", "points": ["...", "..."]}
  ]
}
"""


def _clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


_STOP_WORDS = {
    'a','an','the','of','in','on','at','to','for','with','and','or','is','are',
    'was','were','be','been','having','showing','depicting','photo','image',
    'picture','illustration','drawing','realistic','photograph','students','student',
}


async def _fetch_slide_image(client: httpx.AsyncClient, prompt: str, seed: int) -> str:
    """Fetch a real educational image via Wikipedia REST API; fall back to Picsum."""
    words = re.sub(r'[^\w\s]', '', (prompt or 'science').lower()).split()
    kws = [w for w in words if w not in _STOP_WORDS and len(w) > 3]

    # Try with 3, 2, then 1 keyword combinations
    for n in range(min(3, len(kws)), 0, -1):
        article = '_'.join(kws[:n])
        try:
            r = await client.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(article)}",
                headers={'Accept': 'application/json'},
                timeout=5.0,
            )
            if r.status_code == 200:
                d = r.json()
                # Prefer original full-size image
                orig = d.get('originalimage', {}).get('source', '')
                if orig:
                    return orig
                # Fall back to thumbnail, upscaled
                thumb = d.get('thumbnail', {}).get('source', '')
                if thumb:
                    return re.sub(r'/\d+px-', '/1024px-', thumb)
        except Exception:
            break  # Network error → skip to Picsum

    # Reliable real-photo fallback
    return f"https://picsum.photos/seed/{seed}/1024/576"


async def _attach_image_urls(presentation: dict) -> dict:
    """Fetch real image URLs for all slides in parallel."""
    slides_with_prompts = [
        (i, s) for i, s in enumerate(presentation.get('slides', []), 1)
        if s.get('image_prompt')
    ]
    if not slides_with_prompts:
        return presentation

    async with httpx.AsyncClient(follow_redirects=True, timeout=8.0) as client:
        results = await asyncio.gather(
            *[_fetch_slide_image(client, s['image_prompt'], i) for i, s in slides_with_prompts],
            return_exceptions=True,
        )

    for (i, slide), url in zip(slides_with_prompts, results):
        slide['image_url'] = url if isinstance(url, str) else f"https://picsum.photos/seed/{i}/1024/576"

    return presentation


def _build_user_prompt(subject: str, grade: int, topic: str, language: str) -> str:
    age = grade + 6
    lang_label = LANGUAGE_NAMES.get(language, LANGUAGE_NAMES['uz'])
    return (
        f"Create an interactive educational presentation {lang_label}.\n\n"
        f"Subject: {subject}\n"
        f"Grade: {grade} (students aged ~{age})\n"
        f"Topic: {topic}\n\n"
        f"Generate 8–12 varied slides. Start with a title slide, mix content slides "
        f"with at least 4 interactive slides (quiz / true_false / fill_blank / match / sequence / open_question), "
        f"and end with a summary slide. Include image_prompt (in English) for visual slides."
    )


async def generate_presentation(subject: str, grade: int, topic: str, language: str = 'uz') -> dict:
    """Call Gemini and return a parsed presentation dict with real image URLs attached."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in environment")

    client = genai.Client(api_key=GEMINI_API_KEY)
    user_prompt = _build_user_prompt(subject, grade, topic, language)

    def _call_sync():
        return client.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.8,
                max_output_tokens=8000,
            ),
        )

    response = await asyncio.to_thread(_call_sync)
    raw = response.text or ''
    cleaned = _clean_json(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"AI returned invalid JSON: {e}. Raw: {raw[:500]}")

    if 'slides' not in data or not isinstance(data['slides'], list) or not data['slides']:
        raise RuntimeError("AI response missing 'slides'")

    return await _attach_image_urls(data)
