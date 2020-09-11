import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import TextIOBase

import janus
from asyncio_service import AsyncioService
from tailer import Tailer as PyTailer


logger = logging.getLogger(__name__)


class _FollowThread(AsyncioService):
    threads = list()

    def __init__(self, asynctailer, delay):
        super().__init__(name='Tailer->FollowThread')
        self.queue = janus.Queue()
        self.asynctailer = asynctailer
        self.follow_generator = PyTailer.follow(self.asynctailer, delay=delay)

    def run(self):
        """ override AsyncioService.run() as a synchronous method """
        _FollowThread.threads.append(self)
        try:
            while self.running():
                try:
                    data = next(self.follow_generator)
                    self.queue.sync_q.put(data)
                except (ValueError, StopIteration):
                    break
        finally:
            # warn queue subscriber to stop
            self.queue.sync_q.put(StopIteration)
            _FollowThread.threads.remove(self)

    async def stop(self):
        self.asynctailer.close()
        await super().stop()

    async def run_wrapper(self):
        loop = asyncio.get_running_loop()
        self._running = True
        try:
            await loop.run_in_executor(self.asynctailer.executor, self.run)
        except Exception as e:
            logger.exception(e)
            self.exception = e
        finally:
            self._running = False
            logger.debug(f'closing service: {self.name}')
            await self.close()
            logger.debug(f'service has stopped: {self.name}')

    async def __aiter__(self):
        async with self:
            while self.running() is not True:
                await asyncio.sleep(.01)
            while self.running():
                data = await self.queue.async_q.get()
                if data is StopIteration:
                    break
                else:
                    yield data


class Tailer(PyTailer):
    def __init__(self, file: TextIOBase, read_size: int=1024, end: bool=False, executor: ThreadPoolExecutor=None):
        super().__init__(file, read_size=read_size, end=end)
        self.executor = executor

    async def tail(self, lines=10):
        loop = asyncio.get_running_loop()
        func = partial(super().tail, lines=lines)
        return await loop.run_in_executor(self.executor, func)

    async def head(self, lines=10):
        loop = asyncio.get_running_loop()
        func = partial(super().head, lines=lines)
        return await loop.run_in_executor(self.executor, func)

    async def follow(self, delay=1.0):
        async for line in self.async_follow_thread(delay=delay):
            yield line

    def async_follow_thread(self, delay=1.0):
        return _FollowThread(self, delay=delay)

    @staticmethod
    def follow_threads():
        return _FollowThread.threads

    @staticmethod
    async def stop_follow_threads():
        if len(Tailer.follow_threads()) > 0:
            awaitables = list()
            for t in Tailer.follow_threads():
                awaitables.append(t.stop())
            await asyncio.wait(awaitables)
