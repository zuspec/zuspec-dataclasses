
import dataclasses as dc

@dc.dataclass(kw_only=True)
class io(object):
    pin: int
    nowarn: bool = False


