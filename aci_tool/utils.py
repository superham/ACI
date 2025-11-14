from dateutil import parser
from typing import Optional

# parses date / time strings into datetime objects
def parse_dt(x: Optional[str]):
    if not x:
        return None
    try:
        return parser.parse(x)
    except Exception:
        return None

# safely converts a value to float, returns None if conversion fails
# probably a better way to do this, but it’s a start
# TODO: fix this
def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None
