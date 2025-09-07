import abc

class TypeProcessor(object):

    @abc.abstractmethod
    def new(self, c, *args, **kwargs):
        pass

    @abc.abstractmethod
    def init(self, obj, *args, **kwargs):
        pass
