import datetime
import json
import logging
from typing import Dict, Any, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache season by date string (e.g. "2026-09-30")
_SEASON_CACHE: Dict[str, Dict[str, Any]] = {}


class SeasonService:
    @classmethod
    def _get_fallback_season(cls, target_date: datetime.date) -> Dict[str, Any]:
        month = target_date.month
        year = target_date.year

        if 6 <= month <= 10:
            season_type = "Kharif"
            season_name = f"Kharif Season {year}"
            desc = "Monsoon cropping season (June to October), prominent for rice, cotton, and maize."
        elif month in (11, 12):
            season_type = "Rabi"
            season_name = f"Rabi Season {year}-{year + 1}"
            desc = "Winter cropping season (November to April), prominent for wheat, mustard, and barley."
        elif 1 <= month <= 3:
            season_type = "Rabi"
            season_name = f"Rabi Season {year - 1}-{year}"
            desc = "Winter cropping season (November to April), prominent for wheat, mustard, and barley."
        else:
            season_type = "Zaid"
            season_name = f"Zaid Season {year}"
            desc = "Summer cropping season (March to June), prominent for pulses, melons, and vegetables."

        return {
            "season_name": season_name,
            "season_type": season_type,
            "year": str(year),
            "description": desc,
            "source": "calendar_fallback",
            "date": target_date.isoformat()
        }

    @classmethod
    async def get_current_season(cls, for_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Determines the active Indian agricultural cropping season based on the date using OpenAI.
        Caches the response for the day.
        """
        if for_date:
            try:
                target_date = datetime.date.fromisoformat(for_date)
            except ValueError:
                target_date = datetime.date.today()
        else:
            target_date = datetime.date.today()

        date_key = target_date.isoformat()

        if date_key in _SEASON_CACHE:
            return _SEASON_CACHE[date_key]

        api_key = settings.OPENAI_API_KEY
        if not api_key:
            fallback = cls._get_fallback_season(target_date)
            _SEASON_CACHE[date_key] = fallback
            return fallback

        model = settings.OPENAI_MODEL or "gpt-4o-mini"
        prompt = (
            f"Today's date is {target_date.strftime('%B %d, %Y')} ({date_key}). "
            "Identify the current Indian agricultural cropping season (Kharif, Rabi, or Zaid) and its crop season label. "
            "Respond in strictly valid JSON with the following keys:\n"
            "{\n"
            '  "season_name": "string (e.g. Kharif Season 2026 or Rabi Season 2026-2027)",\n'
            '  "season_type": "string (Kharif, Rabi, or Zaid)",\n'
            '  "year": "string",\n'
            '  "description": "string (brief 1-sentence explanation of this season and timing)"\n'
            "}"
        )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1
                    }
                )

            if res.status_code == 200:
                data = res.json()
                content = json.loads(data["choices"][0]["message"]["content"])
                season_data = {
                    "season_name": content.get("season_name") or cls._get_fallback_season(target_date)["season_name"],
                    "season_type": content.get("season_type") or "Kharif",
                    "year": str(content.get("year", target_date.year)),
                    "description": content.get("description", ""),
                    "source": "openai",
                    "date": date_key
                }
                _SEASON_CACHE[date_key] = season_data
                return season_data
            else:
                logger.warning("OpenAI season query returned status %s; using fallback.", res.status_code)
                fallback = cls._get_fallback_season(target_date)
                _SEASON_CACHE[date_key] = fallback
                return fallback

        except Exception as e:
            logger.warning("Error querying OpenAI for season (%s); using fallback.", e)
            fallback = cls._get_fallback_season(target_date)
            _SEASON_CACHE[date_key] = fallback
            return fallback
