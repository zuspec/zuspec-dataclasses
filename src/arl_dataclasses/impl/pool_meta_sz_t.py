

class PoolMetaSzT(type):

    def __init__(self, name, bases, dct):
        print("PoolMetaSzT: name=%s bases=%s dct=%s" % (name, str(bases), str(dct)))
        self.type_m = {}

    def __getitem__(self, sz):
        from .pool_t import PoolT

        print("PoolMetaSz::__getitem__")
        print("  T=%s" % str(self.T))
        if sz in self.type_m.keys():
            return self.type_m[sz]
        else:
            t = type("pool_t[%s][%d]" % (self.T.__qualname__, sz), (PoolT,), {})
            t.T = self.T
            t.SZ = sz
            self.type_m[sz] = t
            return t

