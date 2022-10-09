

import vsc_dataclasses.impl as vsc_impl


class ModelinfoActivity(vsc_impl.ModelInfo):

    def __init__(self, libobj):
        super().__init__(None, "", None)
        self._libobj = libobj
        self._is_topdown_scope = False # Activities are bottom-up scopes

