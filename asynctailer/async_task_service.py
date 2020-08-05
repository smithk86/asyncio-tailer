import asyncio
import logging
from abc import abstractmethod


logger = logging.getLogger(__name__)


class AsyncTaskService(object):
    def __init__(self, name):
        self.name = name
        self._running = None
        self._task = None

    async def __aenter__(self):
        self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    def start(self):
        loop = asyncio.get_running_loop()
        logger.info(f'starting service: {self.name}')
        self._task = loop.create_task(self.run_wrapper())
        return self._task

    async def stop(self):
        if self._task:
            logger.warning(f'stopping service: {self.name}')
            self._running = False
            await self._task
            self._task = None
            await self.close()

    async def run_wrapper(self):
        self._running = True
        await self.run()
        self._running = False
        logger.debug(f'service has stopped: {self.name}')

    @abstractmethod
    async def run(self):
        pass

    def running(self):
        return self._running

    async def close(self):
        pass
