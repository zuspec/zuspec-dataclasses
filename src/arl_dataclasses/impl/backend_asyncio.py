
import asyncio
from .backend import Backend

class BackendAsyncio(Backend):

    def fork(self, coro):
        return asyncio.create_task(coro)

    async def join(self, task):
        await task
