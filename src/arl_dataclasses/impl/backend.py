
class Backend(object):

    def fork(self, coro):
        raise NotImplementedError("fork for class %s" % str(type(self)))

    async def join(self, task):
        raise NotImplementedError("join for class %s" % str(type(self)))
