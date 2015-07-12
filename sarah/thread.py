# -*- coding: utf-8 -*-
from concurrent.futures.thread import _WorkItem as WorkItem
from concurrent.futures import Executor, Future
import logging
from queue import Queue
import threading
import weakref
import atexit

# Provide the same interface as ThreadPoolExecutor, but create only on thread.
# Worker is created as daemon thread. This is done to allow the interpreter to
# exit when there is still idle thread in ThreadExecutor (i.e. shutdown() was
# not called). However, allowing worker to die with the interpreter has two
# undesirable properties:
#   - The worker would still be running during interpretor shutdown,
#     meaning that they would fail in unpredictable ways.
#   - The worker could be killed while evaluating a work item, which could
#     be bad if the callable being evaluated has external side-effects e.g.
#     writing to a file.
#
# To work around this problem, an exit handler is installed which tells the
# worker to exit when its work queue is empty and then waits until the thread
# finish.

_shutdown = False


def _python_exit():
    global _shutdown
    _shutdown = True


atexit.register(_python_exit)


def _worker(executor_reference, work_queue):
    try:
        while True:
            work_item = work_queue.get(block=True)
            if work_item is not None:
                work_item.run()
                continue
            executor = executor_reference()
            # Exit if:
            #   - The interpreter is shutting down OR
            #   - The executor that owns the worker has been collected OR
            #   - The executor that owns the worker has been shutdown.
            if _shutdown or executor is None or executor._shutdown:
                # Notice other workers
                work_queue.put(None)
                return
            del executor
    except BaseException:
        logging.critical('Exception in worker', exc_info=True)


class ThreadExecuter(Executor):
    def __init__(self):
        """ Initialize a new ThreadExecutor instance. """
        self._work_queue = Queue()
        self._shutdown = False
        self._shutdown_lock = threading.Lock()

        def weakref_cb(_, q=self._work_queue):
            q.put(None)

        t = threading.Thread(target=_worker,
                             args=(weakref.ref(self, weakref_cb),
                                   self._work_queue))
        t.daemon = True
        t.start()
        self._thread = t

    def submit(self, fn, *args, **kwargs):
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError(
                    'cannot schedule new futures after shutdown')

            f = Future()
            w = WorkItem(f, fn, args, kwargs)

            self._work_queue.put(w)
            return f

    submit.__doc__ = Executor.submit.__doc__

    def shutdown(self, wait=True):
        with self._shutdown_lock:
            self._shutdown = True
            self._work_queue.put(None)
        if wait:
            self._thread.join()

    shutdown.__doc__ = Executor.shutdown.__doc__
