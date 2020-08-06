import asyncio
import logging
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import janus
from asyncio_service import AsyncioService
from tailer import Tailer as SyncTailer


logger = logging.getLogger(__name__)


class _FollowThread(AsyncioService):
    def __init__(self, asynctailer, delay):
        super().__init__(name='_AsyncTailerFollowThread')
        self.queue = janus.Queue()
        self.asynctailer = asynctailer
        self.delay = delay

    def start(self):
        """ override start() to execute the non-async run() in an executor """
        loop = asyncio.get_running_loop()
        logger.info(f'starting service: {self.name}')
        self._task = loop.run_in_executor(self.asynctailer.executor, self.run)
        return self._task

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

    async def stop(self):
        self.asynctailer.close()
        await super().stop()

    async def __aiter__(self):
        while self.running:
            yield await self.queue.async_q.get()


class Tailer(object):
    def __init__(self, file, read_size=1024, end=False, max_workers=None):
        self.tailer = SyncTailer(file, read_size, end)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

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
        return _FollowThread(self, delay=delay)

    def close(self):
        self.tailer.file.close()
