"""Stage 2: generate structured recipes from detected ingredients."""

from openai import OpenAI
from pydantic import BaseModel, Field

from .config import OPENAI_API_KEY, VISION_MODEL

SYSTEM_PROMPT = """You are a practical home-cooking chef. The user tells you what is in their fridge.
Suggest 2-3 recipes that:
- Use as many of the detected ingredients as possible (prioritize perishables).
- May also use common staples (oil, salt, pepper, flour, sugar) and at most 2 cheap
  store-cupboard additions the user might need to buy (list them in "missing").
- Match a realistic weeknight effort level (under ~45 min unless it's clearly worth it).
- Have clear, numbered steps a beginner can follow.
Use the user's language for all text (they may write in Ukrainian or English)."""


class Recipe(BaseModel):
    title: str
    description: str = Field(description="one appetizing sentence")
    minutes: int
    difficulty: str = Field(description="easy | medium | hard")
    uses: list[str] = Field(description="fridge ingredients this recipe uses")
    missing: list[str] = Field(description="extra items user might need to buy")
    ingredients: list[str] = Field(description="full ingredient list with amounts")
    steps: list[str]


class RecipeBook(BaseModel):
    recipes: list[Recipe]


_client = OpenAI(api_key=OPENAI_API_KEY)


def generate_recipes(
    ingredient_names: list[str], extras: list[str], preferences: str | None = None
) -> RecipeBook:
    """Turn detected ingredients into 2-3 ranked recipe options."""
    prompt = (
        f"Ingredients in my fridge: {', '.join(ingredient_names)}.\n"
        f"Staples I likely have: {', '.join(extras)}.\n"
    )
    if preferences:
        prompt += f"My dietary preferences/restrictions: {preferences}.\n"
    prompt += "What should I cook? Give me 2-3 options, best use of ingredients first."
    response = _client.beta.chat.completions.parse(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format=RecipeBook,
        max_tokens=2000,
    )
    return response.choices[0].message.parsed


def format_recipe(recipe: Recipe) -> str:
    lines = [
        f"🍳 *{recipe.title}*",
        f"_{recipe.description}_",
        f"⏱ {recipe.minutes} min · 📊 {recipe.difficulty}",
        f"🥕 Uses: {', '.join(recipe.uses)}",
    ]
    if recipe.missing:
        lines.append(f"🛒 You may need: {', '.join(recipe.missing)}")
    lines.append("\n*Ingredients*")
    lines.extend(f"• {i}" for i in recipe.ingredients)
    lines.append("\n*Steps*")
    lines.extend(f"{n}. {s}" for n, s in enumerate(recipe.steps, 1))
    return "\n".join(lines)
