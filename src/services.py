import httpx
from fastapi import HTTPException

ARTIC_ARTWORK_URL = "https://api.artic.edu/api/v1/artworks/{external_id}"
REQUEST_TIMEOUT = 5.0


async def validate_external_place_id(external_id: str) -> bool:
    """Return True if the artwork exists in the Art Institute of Chicago API.

    Raises HTTPException(400) when the artwork is not found, and
    HTTPException(502) when the upstream API cannot be reached.
    """
    url = ARTIC_ARTWORK_URL.format(external_id=external_id)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url)
    except httpx.RequestError as exc:
        # Network-level failure (DNS, connection refused, timeout, etc.)
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach the external places API: {exc}",
        )

    if response.status_code == 200:
        return True

    if response.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail=f"Place with external_id '{external_id}' does not exist.",
        )

    # Unexpected status code from the upstream API
    raise HTTPException(
        status_code=502,
        detail=f"Unexpected response from external places API: {response.status_code}",
    )
