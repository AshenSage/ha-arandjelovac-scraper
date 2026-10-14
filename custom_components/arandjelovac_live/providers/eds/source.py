"""Source contract constants; independent of HA and aiohttp."""
from zoneinfo import ZoneInfo
INDEX_URL = 'https://www.elektrodistribucija.rs/planirana-iskljucenja/planirana-kv'
HOSTS = frozenset({'www.elektrodistribucija.rs', 'elektrodistribucija.rs'})
TZ = ZoneInfo('Europe/Belgrade')
