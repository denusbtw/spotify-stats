import base64
from typing import Iterable


def split_into_batches(items: list, batch_size: int):
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def get_objects_map(model, ids: Iterable[str]) -> dict:
    return {obj.spotify_id: obj for obj in model.objects.filter(spotify_id__in=ids)}


def get_base64_auth_string(client_id: str, client_secret: str) -> str:
    basic_string = f"{client_id}:{client_secret}"
    basic_bytes = basic_string.encode("utf-8")
    basic_bytes_encoded = base64.b64encode(basic_bytes)
    basic_string_decoded = basic_bytes_encoded.decode("utf-8")
    return basic_string_decoded


def safe_strip(value: str) -> str | None:
    return value.strip() if isinstance(value, str) else None
