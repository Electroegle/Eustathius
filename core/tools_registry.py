import asyncio


class Tool:
    def __init__(self, name, description, func):
        self.name = name; self.description = description; self.func = func

class ToolRegistry:
    def __init__(self): self.tools: dict[str, Tool] = {}
    def register(self, tool: Tool): self.tools[tool.name] = tool
    def list_names(self): return list(self.tools.keys())
    def describe(self):
        return "\n".join(f"- {tool.name}: {tool.description}" for tool in self.tools.values())
    async def execute(self, name, args_str):
        if name not in self.tools: return f"Tool '{name}' not found."
        return await self.tools[name].func(args_str)

async def weather_tool(args):
    import httpx
    city = args.strip()
    async with httpx.AsyncClient() as client:
        geo = await client.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1")
        data = geo.json()
        if not data.get("results"): return "City not found."
        loc = data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        wresp = await client.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true")
        w = wresp.json()["current_weather"]
        return f"{loc['name']}: {w['temperature']}°C, wind {w['windspeed']} km/h"

async def search_tool(args):
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    query = args.strip()
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))
    return "\n".join(f"{r['title']}: {r['body']}" for r in results)

async def code_exec_tool(args):
    proc = await asyncio.create_subprocess_exec("python", "-c", args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    return stdout.decode() + ("\n" + stderr.decode() if stderr else "")

def create_default_tools():
    registry = ToolRegistry()
    registry.register(Tool("weather", "Get weather for a city", weather_tool))
    registry.register(Tool("search", "Search the internet", search_tool))
    registry.register(Tool("code_exec", "Execute Python code", code_exec_tool))
    return registry
