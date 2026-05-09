import psutil
def get_cpu_percent(): return psutil.cpu_percent(interval=0.1)
def get_memory_percent(): return psutil.virtual_memory().percent
def is_system_under_load(cpu=80, mem=85): return get_cpu_percent()>cpu or get_memory_percent()>mem
def system_stats(): return {"cpu_percent": get_cpu_percent(), "memory_percent": get_memory_percent()}
