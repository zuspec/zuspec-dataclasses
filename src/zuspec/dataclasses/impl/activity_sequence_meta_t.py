
from .activity_sequence_impl import ActivitySequenceImpl


class ActivitySequenceMetaT(type):

    def __init__(self, name, bases, dct):
        self.seq_s = []
        pass

    def __enter__(self):
        seq = ActivitySequenceImpl()
        self.seq_s.append(seq)
        return seq.__enter__()

    def __exit__(self, t, v, tb):
        self.seq_s[-1].__exit__(t, v, tb)
        self.seq_s.pop()

