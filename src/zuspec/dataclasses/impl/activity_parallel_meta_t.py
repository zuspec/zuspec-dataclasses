
from .activity_parallel_impl import ActivityParallelImpl

class ActivityParallelMetaT(type):

    def __init__(self, name, bases, dct):
        self.par_s = []
        pass

    def __enter__(self):
        par = ActivityParallelImpl()
        self.par_s.append(par)
        return par.__enter__()

    def __exit__(self, t, v, tb):
        self.par_s[-1].__exit__(t, v, tb)
        self.par_s.pop()
