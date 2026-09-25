import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def session_with_retries() -> requests.Session:
    # Retry transient upstream failures (502/503/504) and rate limits (429),
    # plus connection errors / read timeouts handled by urllib3 by default.
    retry = Retry(
        total=4,
        backoff_factor=2,  # 2s, 4s, 8s, 16s
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s
