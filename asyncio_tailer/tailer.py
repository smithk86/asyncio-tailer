from __future__ import annotations

import asyncio
import time
from pathlib import Path

from typing import TYPE_CHECKING

from asyncio_generator_converter import asyncio_generator_converter
from tailer import Tailer as BaseTailer


if TYPE_CHECKING:
    from io import TextIOBase
    from typing import Any, Callable, Generator, List, Optional, Type


NoneType: Type = type(None)


class Tailer:
    def __init__(
        self,
        file: TextIOBase,
        read_size: int = 1024,
        end: bool = False,
    ):
        self._base_tailer: BaseTailer = BaseTailer(file, read_size=read_size, end=end)
        self._follow_running: bool = False

    @property
    def path(self):
        return Path(self._base_tailer.file.name)

    def close(self) -> None:
        self._base_tailer.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_tailer, name)

    async def tail(self, lines: int = 10) -> List[str]:
        return await asyncio.to_thread(self._base_tailer.tail, lines=lines)

    async def head(self, lines: int = 10) -> List[str]:
        return await asyncio.to_thread(self._base_tailer.head, lines=lines)

    def stop_following(self) -> None:
        self._follow_running = False

    @asyncio_generator_converter
    def follow(self, delay=1.0) -> Generator:
        """
        based on Tailer.follow in https://github.com/six8/pytailer.git@0.4.1

        Mostly the same code with a way to break out of the loop
        """
        trailing = True
        self._follow_running = True
        while self._follow_running:
            where = self._base_tailer.file.tell()
            line = self._base_tailer.file.readline()
            if line:
                if trailing and line in self._base_tailer.line_terminators:
                    # This is just the line terminator added to the end of the file
                    # before a new line, ignore.
                    trailing = False
                    continue

                if line[-1] in self._base_tailer.line_terminators:
                    line = line[:-1]
                    if (
                        line[-1:] == "\r\n"
                        and "\r\n" in self._base_tailer.line_terminators
                    ):
                        # found crlf
                        line = line[:-1]

                trailing = False
                yield line
            else:
                trailing = True
                self._base_tailer.seek(where)
                time.sleep(delay)
