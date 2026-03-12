from datetime import UTC, datetime
from uuid import uuid4


def generate_id(prefix: str) -> str:
    now = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
    token = uuid4().hex[:12]
    return f"{prefix}_{now}_{token}"
