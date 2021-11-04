from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import TextIOBase
from typing import TYPE_CHECKING

import janus
from asyncio_service import AsyncioService
from tailer import Tailer as BaseTailer   # type: ignore


if TYPE_CHECKING:
    from concurrent.futures import Executor
    from typing import Any, AsyncGenerator, Callable, Generator, List, Optional, Union

    Number = Union[int, float]
    QueueValueTypes = Union[str, StopIteration]
    JanusAsyncQueue = janus._AsyncQueueProxy[QueueValueTypes]


logger = logging.getLogger(__name__)


class _FollowThread(AsyncioService):
    def __init__(self, asynctailer: Tailer, delay: Number):
        filename: str = asynctailer.file.name
        super().__init__(name=f'Tailer->FollowThread [file={filename}]')
        self.queue: janus.Queue[QueueValueTypes] = janus.Queue()
        self._asynctailer: Tailer = asynctailer
        self._follow_generator: Generator = BaseTailer.follow(self._asynctailer, delay=delay)

        @self.cleanup
        def _alert_subscriber(self, **kwargs):
            """ warn queue subscriber to stop """
            self.queue.sync_q.put(StopIteration)

    @property
    def running(self) -> bool:
        return not self._stop.is_set()

    async def run(self) -> None:
        def _sync():
            while self.running:
                try:
                    _data = next(self._follow_generator)
                    self.queue.sync_q.put(_data)
                except (ValueError, StopIteration):
                    break
        await self._asynctailer._run_in_executor(_sync)

    async def stop(self) -> None:
        self._asynctailer.close()
        await super().stop()

    async def __aiter__(self) -> AsyncGenerator:
        async with self:
            while self.running:
                _data = await self.queue.async_q.get()
                if _data is StopIteration:
                    break
                else:
                    yield _data


class Tailer(BaseTailer):
    def __init__(
        self,
        file: TextIOBase,
        read_size: int = 1024,
        end: bool = False,
        executor: Optional[Executor] = None
    ):
        super().__init__(file, read_size=read_size, end=end)
        self.executor: Optional[Executor] = executor
        self.follow_thread: Optional[_FollowThread] = None

    async def _run_in_executor(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        _loop = asyncio.get_running_loop()
        _func = partial(func, *args, **kwargs)
        return await _loop.run_in_executor(self.executor, _func)

    async def tail(self, lines: int = 10) -> List[str]:
        return await self._run_in_executor(super().tail, lines=lines)

    async def head(self, lines: int = 10) -> List[str]:
        return await self._run_in_executor(super().head, lines=lines)

    async def follow(self, delay: Number = 1.0) -> AsyncGenerator:
        if self.follow_thread is None:
            self.follow_thread = _FollowThread(self, delay=delay)

        try:
            async for line in self.follow_thread:
                yield line
        finally:
            self.follow_thread = None

    async def start_follow_thread(self, delay: Number = 1.0) -> None:
        if self.follow_thread is not None:
            raise RuntimeError('an instance of _FollowThread is already active')

        self.follow_thread = _FollowThread(self, delay=delay)
        self.follow_thread.start()
        await self.follow_thread.ready()

    async def stop_follow_thread(self) -> None:
        if self.follow_thread:
            self.follow_thread.stop()
            await self.follow_thread.join()
            self.follow_thread = None

    @property
    def follow_queue(self) -> Optional[JanusAsyncQueue]:
        if self.follow_thread:
            return self.follow_thread.queue.async_q
        else:
            return None
