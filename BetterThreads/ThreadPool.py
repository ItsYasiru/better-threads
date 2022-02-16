import time
from threading import Thread, Lock
from typing import Callable, Union

from BetterThreads.PooledThread import PooledThread


class ThreadPool:
    def __init__(self):
        self.__lock: Lock = Lock()
        self.__threads: dict[Callable, PooledThread] = dict()
        self.__dead_threads: dict[Callable, PooledThread] = dict()

    def __len__(self):
        threads = self.__threads.copy()
        for func, thread in threads.items():
            if not thread.is_alive():
                with self.__lock: self.__dead_threads[func] = self.__threads.pop(func)

        dead_threads = self.__dead_threads.copy()
        for func, thread in dead_threads.items():
            if thread.is_alive():
                with self.__lock: self.__threads[func] = self.__dead_threads.pop(func)

        return len(self.__threads)

    def thread(self):
        def wrapper(func: Union[Callable, PooledThread], *args, **kwargs):
            self.add_thread(func, *args, **kwargs)
        return wrapper

    def add_thread(self, func: Union[Callable, PooledThread], *args, **kwargs):
        with self.__lock:
            if isinstance(func, PooledThread):
                self.__threads[func._PooledThread__target] = func
            else:
                thread = PooledThread(func, *args, **kwargs)
                self.__threads[func] = thread
                return thread

    def terminate(self, func: Callable = None, block: bool = None, timeout: int = None):
        thread = self.get_thread(func)

        if thread:
            thread.terminate(block=block, timeout=timeout)
            with self.__lock: del self.__threads[func]

    def terminate_all(self, *, block: bool = True, timeout: int = None):
        """Terminates all threads in the pool"""
        for thread in self.__threads.values():
            thread.terminate(block=False)

        if block:
            start = time.time()
            while any(thread.is_alive() for thread in self.__threads.values()):
                if timeout:
                    if time.time() - start > timeout: break
            with self.__lock: self.__threads = dict()

    def pause(self, func: Callable = None, *, resume_in: int = None, block: bool = True, timeout: int = None):
        def resume_dummy():
            time.sleep(resume_in)
            thread.resume()

        thread = self.get_thread(func)

        if thread:
            if resume_in:
                Thread(target=resume_dummy).start()
            thread.pause(block=block, timeout=timeout)

    def pause_all(self, *, resume_in: int = None, block: bool = True, timeout: int = None):
        """Pause all the threads in the pool"""
        def dummy_thread():
            time.sleep(resume_in)
            self.resume_all(block=False)

        for thread in self.__threads.values():
            thread.pause(block=False)

        if resume_in: Thread(target=dummy_thread).start()

        if block:
            start = time.time()
            while any(not thread.is_paused() for thread in self.__threads.values()):
                if timeout:
                    if time.time() - start > timeout: break

    def resume(self, func: Callable = None):
        thread = self.get_thread(func)

        if thread: thread.resume()

    def resume_all(self, *, block: bool = True):
        """Resume all the threads in the pool"""
        for thread in self.__threads.values():
            thread.pause(block=False)

        if block:
            while any(thread.is_paused() for thread in self.__threads.values()): pass

    def get_thread(self, func: Union[Callable, PooledThread] = None) -> Union[PooledThread, None]:
        for thread in self.__threads.values():
            if func == thread._PooledThread__target: return thread
            if func == thread: return thread

    @staticmethod
    def get_pipe(feed, pipe_out):
        """Builds a pipe function to pipe data between threads"""
        def pipe(data: dict = None):
            if data:
                return pipe_out(data)
            else:
                return feed()
        return pipe
