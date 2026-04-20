"""Gemini-powered AI presentation generator."""
import json
import os
import re
import asyncio
from typing import Optional
from urllib.parse import quote

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
- Make it INTERACTIVE: include quizzes, true/false, fill-in-the-blank, and matching exercises.
- Provide rich, accurate, age-appropriate information on the topic.
- For every slide that benefits from a visual, include an `image_prompt` field in ENGLISH (it is used by an image generator) describing what to show. Do NOT translate image_prompt — keep it English.
- Aim for 8–12 slides total. Mix slide types for variety.
- For quizzes: 4 options, the index of the correct answer (0-3), and a short explanation.
- For matching: 3–5 pairs of [left, right] items.
- For fill-in-the-blank: a sentence with `___` where the blank is, plus the correct answer.

Return ONLY valid JSON matching this schema (no markdown, no commentary):
{
  "title": "string (presentation title)",
  "subtitle": "string (short hook / age group)",
  "slides": [
    {"type": "title", "title": "...", "subtitle": "...", "image_prompt": "..."},
    {"type": "content", "title": "...", "points": ["...", "..."], "image_prompt": "..."},
    {"type": "image_focus", "title": "...", "caption": "...", "image_prompt": "..."},
    {"type": "quiz", "question": "...", "options": ["A", "B", "C", "D"], "correct": 0, "explanation": "..."},
    {"type": "true_false", "statement": "...", "is_true": true, "explanation": "..."},
    {"type": "fill_blank", "title": "...", "sentence": "Sun is a ___.", "answer": "star", "hint": "..."},
    {"type": "match", "title": "...", "pairs": [["left1","right1"], ["left2","right2"]]},
    {"type": "summary", "title": "...", "points": ["...", "..."]}
  ]
}
"""


def _clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _image_url(prompt: str, seed: int = 1, width: int = 1024, height: int = 576) -> str:
    """Pollinations.ai — free, no API key, returns an image directly from URL."""
    encoded = quote((prompt or 'school education classroom').strip()[:300])
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&seed={seed}&nologo=true&model=flux"
    )


def _attach_image_urls(presentation: dict) -> dict:
    """Mutates slides to include `image_url` derived from each slide's image_prompt."""
    for i, slide in enumerate(presentation.get('slides', []), start=1):
        prompt = slide.get('image_prompt')
        if prompt:
            slide['image_url'] = _image_url(prompt, seed=i)
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
        f"with at least 3 interactive slides (quiz / true_false / fill_blank / match), "
        f"and end with a summary slide. Include image_prompt (in English) for visual slides."
    )


async def generate_presentation(subject: str, grade: int, topic: str, language: str = 'uz') -> dict:
    """Call Gemini and return a parsed presentation dict with image URLs attached."""
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

    return _attach_image_urls(data)
