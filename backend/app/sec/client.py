import httpx
import tenacity

from backend.app.core.config import settings


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


# A full-universe pull makes thousands of sequential requests; a lone
# transient blip (429/5xx/timeout) must not kill the whole run. Client
# errors (4xx other than 429) are never retried -- they will not succeed
# on retry and retrying just burns SEC's rate-limit budget.
_retry_transient = tenacity.retry(
    retry=tenacity.retry_if_exception(_is_transient),
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)


class SecOpenDataClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else settings.sec_api_key
        self.base_url = (base_url or settings.sec_api_base_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Cache-Control": "no-cache",
            "Accept": "application/json",
        }

    @_retry_transient
    def get(self, path: str, params: dict | None = None):
        url = f"{self.base_url}{path}"
        response = httpx.get(url, headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        if response.status_code == 204 or not response.content.strip():
            return {}
        return response.json()

    @_retry_transient
    def post(self, path: str, payload: dict | list | None = None):
        url = f"{self.base_url}{path}"
        response = httpx.post(url, headers=self._headers(), json=payload or {}, timeout=30)
        response.raise_for_status()
        if response.status_code == 204 or not response.content.strip():
            return {}
        return response.json()
