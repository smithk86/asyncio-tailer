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

    QueueValueTypes = Union[str, StopIteration]
    JanusAsyncQueue = janus._AsyncQueueProxy[QueueValueTypes]


logger = logging.getLogger(__name__)


class TailerFollowThread(AsyncioService):
    def __init__(self, tailer: Tailer, delay: float):
        super().__init__(name=f'TailerFollowThread [file={tailer.filename}]')
        self._tailer = tailer
        self._delay = delay
        self.queue: janus.Queue[QueueValueTypes] = janus.Queue()

        @self.cleanup
        def _alert_subscriber(self, **kwargs):
            """ warn queue subscriber to stop """
            self.queue.sync_q.put(StopIteration)

    @property
    def running(self) -> bool:
        return not self._stop.is_set()

    async def run(self) -> None:
        def _sync():
            _follow_generator = self._tailer._base_tailer.follow(self._delay)
            while self.running:
                try:
                    _data = next(_follow_generator)
                    self.queue.sync_q.put(_data)
                except (ValueError, StopIteration) as e:
                    break
        await self._tailer._run_in_executor(_sync)

    async def stop(self) -> None:
        self._tailer.close()
        await super().stop()

    async def __aiter__(self) -> AsyncGenerator:
        async with self:
            while self.running:
                _data = await self.queue.async_q.get()
                if _data is StopIteration:
                    break
                else:
                    yield _data


class Tailer:
    def __init__(
        self,
        file: TextIOBase,
        read_size: int = 1024,
        end: bool = False,
        executor: Optional[Executor] = None
    ):
        self._base_tailer: BaseTailer = BaseTailer(file, read_size=read_size, end=end)
        self.executor: Optional[Executor] = executor

    @property
    def filename(self):
        return self._base_tailer.file.name

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_tailer, name)

    async def _run_in_executor(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        _loop = asyncio.get_running_loop()
        _func = partial(func, *args, **kwargs)
        return await _loop.run_in_executor(self.executor, _func)

    async def tail(self, lines: int = 10) -> List[str]:
        return await self._run_in_executor(self._base_tailer.tail, lines=lines)

    async def head(self, lines: int = 10) -> List[str]:
        return await self._run_in_executor(self._base_tailer.head, lines=lines)

    def follow(self, delay: float = 1.0) -> AsyncGenerator:
        return self.get_follow_thread(delay).__aiter__()

    def get_follow_thread(self, delay: float = 1.0) -> TailerFollowThread:
        return TailerFollowThread(self, delay=delay)

    def close(self) -> None:
        self._base_tailer.close()
