import asyncio
from abc import abstractmethod


class AsyncThread(object):
    def __init__(self):
        self.running = None
        self.task = None

    async def __aenter__(self):
        self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    async def stop(self):
        self.running = False
        await self.task

    def start(self):
        loop = asyncio.get_running_loop()
        self.task = loop.create_task(self._run())

    async def _run(self):
        self.running = True
        await self.run()

    @abstractmethod
    async def run(self):
        pass


class AsyncThreadWithExecutor(AsyncThread):
    def __init__(self, executor=None):
        super().__init__()
        self.executor = executor

    def start(self):
        loop = asyncio.get_running_loop()
        self.task = loop.run_in_executor(self.executor, self._run)

    def _run(self):
        self.running = True
        self.run()

    @abstractmethod
    def run(self):
        pass
