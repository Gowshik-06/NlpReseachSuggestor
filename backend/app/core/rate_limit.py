"""
Rate limiting configuration and reverse-proxy aware client IP resolver using slowapi.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_client_ip(request: Request) -> str:
    """
    Determine client IP address safely to prevent accidental cross-user lockouts.

    Trusts X-Forwarded-For and X-Real-IP headers ONLY if the direct connection originates
    from a verified reverse proxy listed in TRUSTED_PROXIES. Otherwise uses the immediate
    socket client IP. Never logs user credentials or tokens.
    """
    settings = get_settings()
    client_host = request.client.host if request.client else "127.0.0.1"
    trusted_proxies = set(getattr(settings, "TRUSTED_PROXIES", ["127.0.0.1", "::1"]))

    is_trusted = client_host in trusted_proxies
    if not is_trusted:
        try:
            import ipaddress
            client_ip_obj = ipaddress.ip_address(client_host)
            for proxy_entry in trusted_proxies:
                if "/" in proxy_entry:
                    if client_ip_obj in ipaddress.ip_network(proxy_entry, strict=False):
                        is_trusted = True
                        break
        except Exception:
            pass

    if is_trusted:
        # Evaluate X-Forwarded-For: client is the leftmost IP
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if forwarded:
            ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
            if ips:
                return ips[0]

        real_ip = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
        if real_ip and real_ip.strip():
            return real_ip.strip()

    return client_host


settings = get_settings()
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[],
    enabled=getattr(settings, "ENABLE_RATE_LIMITING", True),
)
