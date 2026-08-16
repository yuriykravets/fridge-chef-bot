"""Stage 1: detect ingredients in fridge photos using a vision LLM."""

from base64 import b64encode

from openai import OpenAI
from pydantic import BaseModel

from .config import OPENAI_API_KEY, VISION_MODEL

SYSTEM_PROMPT = """You are a kitchen assistant. The user sends photos of their fridge or pantry.
Identify every food item you can see. Be pragmatic:
- Merge duplicates (two photos of the same milk carton = one item).
- Include quantities only if obvious (e.g. "3 eggs").
- If an item is ambiguous (could be butter or cheese), set confidence to "low".
- Ignore non-food items and packaging you cannot see into.
- Add a short "possible_extras" guess list of common staples the person likely owns
  (oil, salt, pepper, flour, sugar) so recipes can use them.
The user's message asks for ingredients; respond with structured JSON only."""


class Ingredient(BaseModel):
    name: str
    quantity: str | None = None
    confidence: str = "high"  # high | medium | low


class FridgeAnalysis(BaseModel):
    ingredients: list[Ingredient]
    possible_extras: list[str]


_client = OpenAI(api_key=OPENAI_API_KEY)


def analyze_fridge_photos(photo_bytes_list: list[bytes]) -> FridgeAnalysis:
    """Send 1-3 photos to the vision model, return structured ingredients."""
    content: list[dict] = [{"type": "text", "text": "What food items are in these fridge photos?"}]
    for photo_bytes in photo_bytes_list:
        b64 = b64encode(photo_bytes).decode("utf-8")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            }
        )

    response = _client.beta.chat.completions.parse(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format=FridgeAnalysis,
        max_tokens=1000,
    )
    return response.choices[0].message.parsed


def format_analysis(analysis: FridgeAnalysis) -> str:
    lines = ["🥗 *What I found in your fridge:*\n"]
    icons = {"high": "✅", "medium": "🤔", "low": "❓"}
    for item in analysis.ingredients:
        qty = f" — {item.quantity}" if item.quantity else ""
        lines.append(f"{icons.get(item.confidence, '•')} {item.name}{qty}")
    if analysis.possible_extras:
        lines.append(
            f"\n🧂 I'll assume you also have: {', '.join(analysis.possible_extras)}"
        )
    lines.append("\n📸 Send more photos, or /done when ready.")
    return "\n".join(lines)
