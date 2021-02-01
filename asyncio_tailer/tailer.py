import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import TextIOBase

import janus
from asyncio_service import AsyncioService
from asyncio_service.service import now
from tailer import Tailer as PyTailer


logger = logging.getLogger(__name__)


class _FollowThread(AsyncioService):
    threads = list()

    def __init__(self, asynctailer, delay):
        filename = asynctailer.file.name
        super().__init__(name=f'Tailer->FollowThread [file={filename}]')
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
        self.start_date = now()
        try:
            await self.asynctailer.loop.run_in_executor(self.asynctailer.executor, self.run)
        except Exception as e:
            logger.exception(e)
            self.exception = e
        finally:
            self.end_date = now()
            logger.debug(f'closing service: {self.name}')
            await self.cleanup()
            logger.debug(f'service has stopped: {self.name}')

            if self in AsyncioService._running_services:
                AsyncioService._running_services.remove(self)
            else:
                logger.warning('this service was not found in AsyncioService._running_services [name={self.name}]')

    async def __aiter__(self):
        async with self:
            await self.wait_for_running()
            while self.running():
                data = await self.queue.async_q.get()
                if data is StopIteration:
                    break
                else:
                    yield data


class Tailer(PyTailer):
    def __init__(self, file: TextIOBase, read_size: int = 1024, end: bool = False, executor: ThreadPoolExecutor = None):
        super().__init__(file, read_size=read_size, end=end)
        self.executor = executor
        self.follow_thread = None

    @property
    def loop(self):
        return asyncio.get_running_loop()

    async def tail(self, lines=10):
        func = partial(super().tail, lines=lines)
        return await self.loop.run_in_executor(self.executor, func)

    async def head(self, lines=10):
        func = partial(super().head, lines=lines)
        return await self.loop.run_in_executor(self.executor, func)

    async def follow(self, delay=1.0):
        if self.follow_thread is None:
            self.follow_thread = _FollowThread(self, delay=delay)

        try:
            async for line in self.follow_thread:
                yield line
        finally:
            self.follow_thread = None

    async def start_follow_thread(self, delay=1.0):
        if self.follow_thread is not None:
            raise RuntimeError('an instance of _FollowThread is already active')

        self.follow_thread = _FollowThread(self, delay=delay)
        self.follow_thread.start()
        await self.follow_thread.wait_for_running()

    async def stop_follow_thread(self):
        if self.follow_thread:
            await self.follow_thread.stop()
            self.follow_thread = None

    @property
    def follow_queue(self):
        if self.follow_thread:
            return self.follow_thread.queue.async_q
        else:
            return None

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
