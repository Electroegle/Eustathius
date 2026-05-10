import httpx

from . import SkillBase


class WeatherSkill(SkillBase):
    name="weather"; description="Get current weather for a city."
    keywords=["weather","temperature","forecast","rain","humidity"]
    async def execute(self, task, model, council=False, **kwargs):
        city = task.lower().replace("weather","").replace("temperature","").strip()
        async with httpx.AsyncClient() as client:
            geo = await client.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1")
            if geo.status_code!=200: return "City not found."
            data = geo.json()
            if not data.get("results"): return "City not found."
            loc = data["results"][0]; lat, lon = loc["latitude"], loc["longitude"]
            w = await client.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true")
            weather = w.json()["current_weather"]
            return f"{loc['name']}: {weather['temperature']}°C, wind {weather['windspeed']} km/h"
