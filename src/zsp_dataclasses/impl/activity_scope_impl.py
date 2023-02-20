
class ActivityScopeImpl(object):

    def __init__(self, *args, **kwargs):
        if len(args) > 0:
            raise Exception("scope does not support positional arguments")
        
        if "label" in kwargs.keys():
            print("Labeled scope")
            self.name = kwargs["label"]
        else:
            self.name = None

        self.scope = None
        self.subscopes_m = {}
        pass

