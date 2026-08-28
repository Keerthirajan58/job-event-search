"""Polite, cached HTTP. Stdlib only.

Rules enforced here so no call site can violate them:
  * one shared UA that identifies the tool and a contact address
  * per-host minimum interval (we throttle ourselves; we never race a rate limit)
  * bounded retries with backoff, and we STOP on 401/403/429 rather than retrying
    around an access control
  * on-disk response cache so re-runs during a day cost the sites nothing
"""
import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

_last_hit = {}
_stats = {"fetched": 0, "cached": 0, "failed": 0, "blocked": 0}


class Blocked(Exception):
    """Server signalled we must not proceed (auth wall / rate limit)."""


def stats():
    return dict(_stats)


def _cache_path(url):
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return os.path.join(config.CACHE_DIR, h + ".gz")


def _throttle(url):
    host = urllib.parse.urlparse(url).netloc
    wait = config.HTTP_MIN_INTERVAL - (time.time() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.time()


def get(url, accept="text/html,application/json", use_cache=True, ttl=None):
    """Return response body as str, or raise Blocked / urllib errors."""
    ttl = config.CACHE_TTL_SECONDS if ttl is None else ttl
    cp = _cache_path(url)
    if use_cache and os.path.exists(cp) and (time.time() - os.path.getmtime(cp)) < ttl:
        _stats["cached"] += 1
        with gzip.open(cp, "rt", encoding="utf-8") as fh:
            return fh.read()

    last = None
    for attempt in range(config.HTTP_RETRIES):
        _throttle(url)
        req = urllib.request.Request(url, headers={
            "User-Agent": config.HTTP_UA,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                body = raw.decode("utf-8", "replace")
            _stats["fetched"] += 1
            with gzip.open(cp, "wt", encoding="utf-8") as fh:
                fh.write(body)
            return body
        except urllib.error.HTTPError as e:
            # Never retry around an access control or a rate limit.
            if e.code in (401, 403, 429):
                _stats["blocked"] += 1
                raise Blocked("HTTP %s for %s" % (e.code, url))
            last = e
            if e.code == 404:
                break
        except Exception as e:                      # timeout, DNS, reset
            last = e
        time.sleep(1.5 * (attempt + 1))
    _stats["failed"] += 1
    raise last if last else RuntimeError("fetch failed: " + url)


def get_json(url, **kw):
    kw.setdefault("accept", "application/json")
    return json.loads(get(url, **kw))
