from __future__ import annotations

import asyncio
from functools import partial

from typing import TYPE_CHECKING

from asyncio_generator_converter import asyncio_generator_converter
from tailer import Tailer as BaseTailer


if TYPE_CHECKING:
    from concurrent.futures import Executor
    from io import TextIOBase
    from typing import Any, Callable, Generator, List, Optional


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
