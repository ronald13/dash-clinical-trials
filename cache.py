from flask_caching import Cache
from app import app

cache = Cache(app.server, config={
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
})
