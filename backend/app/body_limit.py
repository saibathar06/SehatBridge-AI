from starlette.types import ASGIApp, Scope, Receive, Send
from fastapi import HTTPException


class BodyLimitMiddleware:
    """Bound chunked uploads too, before Starlette's multipart parser spools them."""
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get('body', b''))
            if received > self.max_bytes:
                raise HTTPException(413, 'Payload exceeds size limit')
            return message

        await self.app(scope, bounded_receive, send)
