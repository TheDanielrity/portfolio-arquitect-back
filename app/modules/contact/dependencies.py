from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, ip_address

from fastapi import Request

from app.modules.media.storage import database_text


@dataclass(frozen=True)
class SubmissionContext:
    ip_address: IPv4Address | IPv6Address | None
    user_agent: str | None


async def get_submission_context(request: Request) -> SubmissionContext:
    """Submission policy boundary for future CAPTCHA and spam-check dependencies.

    Only the ASGI peer is used; forwarded headers are not trusted here. Any proxy
    trust must be configured at the server. Request middleware applies peer limits.
    """
    address = None
    if request.client is not None:
        try:
            address = ip_address(request.client.host)
        except ValueError:
            pass
    user_agent = request.headers.get("user-agent", "")[:1024] or None
    if user_agent is not None:
        try:
            database_text(user_agent)
        except ValueError:
            user_agent = None
    return SubmissionContext(address, user_agent)
