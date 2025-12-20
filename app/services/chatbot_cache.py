from functools import lru_cache
import hashlib

_answer_cache = {}

@lru_cache(maxsize=100)
def _get_cached_answer_hash(message_hash: str):
    return None

def get_cached_answer(message: str) -> str:
    message_hash = hashlib.md5(message.lower().strip().encode()).hexdigest()
    cached = _answer_cache.get(message_hash)
    return cached

def save_to_cache(message: str, answer: str):
    message_hash = hashlib.md5(message.lower().strip().encode()).hexdigest()
    _answer_cache[message_hash] = answer
    return message_hash

def clear_cache():
    _answer_cache.clear()
    _get_cached_answer_hash.cache_clear()

