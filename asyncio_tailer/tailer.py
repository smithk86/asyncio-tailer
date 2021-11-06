from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import TextIOBase
from typing import TYPE_CHECKING

import janus
from tailer import Tailer as BaseTailer


if TYPE_CHECKING:
    from concurrent.futures import Executor
    from typing import Any, AsyncGenerator, Callable, Generator, List, Optional


def asyncio_generator_converter(func) -> Callable:
    def _consumer(generator: Generator, queue: janus.Queue) -> None:
        for _data in generator:
            queue.sync_q.put(_data)

    async def _run_consumer(executor: ThreadPoolExecutor, func: Callable):
        _loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        await _loop.run_in_executor(executor, func)

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> AsyncGenerator:
        _executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)
        _generator: Generator = func(*args, **kwargs)
        _queue: janus.Queue = janus.Queue()
        _task: asyncio.Task = asyncio.create_task(
            _run_consumer(
                _executor,
                partial(_consumer, _generator, _queue)
            )
        )
        try:
            while not _task.done():
                try:
                    _data = await asyncio.wait_for(_queue.async_q.get(), 1)
                    yield _data
                except asyncio.TimeoutError:
                    pass
            while _queue.async_q.qsize() > 0:
                yield await _queue.async_q.get()
        finally:
            _executor.shutdown()
    return wrapper


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

    @asyncio_generator_converter
    def follow(self, delay: float = 1.0) -> Generator:
        try:
            for _data in self._base_tailer.follow(delay):
                yield _data
        except ValueError:
            pass
