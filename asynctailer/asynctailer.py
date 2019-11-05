import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import janus
from tailer import Tailer

from .async_thread import AsyncThreadWithExecutor


class _AsyncTailerFollowThread(AsyncThreadWithExecutor):
    def __init__(self, asynctailer, delay):
        super().__init__(executor=asynctailer.executor)
        self.queue = janus.Queue()
        self.asynctailer = asynctailer
        self.delay = delay

    def run(self):
        iter_ = self.asynctailer.tailer.follow(delay=self.delay)
        while self.running:
            try:
                data = next(iter_)
            except (ValueError, StopIteration):
                self.queue.sync_q.put(StopIteration)
                self.running = False
            else:
                self.queue.sync_q.put(data)

    async def __aiter__(self):
        while self.running:
            yield await self.queue.async_q.get()


class AsyncTailer(object):
    def __init__(self, file, read_size=1024, end=False, executor_max_workers=None):
        self.tailer = Tailer(file, read_size, end)
        self.executor = ThreadPoolExecutor(max_workers=executor_max_workers)

    async def tail(self, lines=10):
        loop = asyncio.get_running_loop()
        func = partial(self.tailer.tail, lines=lines)
        return await loop.run_in_executor(self.executor, func)

    async def head(self, lines=10):
        loop = asyncio.get_running_loop()
        func = partial(self.tailer.head, lines=lines)
        return await loop.run_in_executor(self.executor, func)

    async def follow(self, delay=1.0):
        async with self.async_follow_thread(delay=delay) as follower:
            async for line in follower:
                yield line

    def async_follow_thread(self, delay=1.0):
        return _AsyncTailerFollowThread(self, delay=delay)

    def close(self):
        self.tailer.file.close()
