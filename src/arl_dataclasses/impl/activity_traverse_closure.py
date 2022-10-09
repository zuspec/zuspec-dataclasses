'''
Created on Jun 15, 2022

@author: mballance
'''
import vsc_dataclasses.impl as vsc_impl


class ActivityTraverseClosure(object):
    
    def __init__(self, traverse_t, field):
        self.traverse_t = traverse_t
        self.field = field
        pass
    
    def __call__(self, *args, **kwargs):
        if len(args) > 0:
            # TODO: it's okay if we're traversing an activity lambda
            raise Exception("Can only pass kwargs to an action traversal")
        print("__call__: %s %s" % (str(args), str(kwargs)))
        return self
        pass
    
    def __enter__(self):
        print("enter")
        ctor = vsc_impl.Ctor.inst()
        ctor.push_expr_mode()
        c = ctor.ctxt().mkTypeConstraintScope()
        self.traverse_t.setWithC(c)
        
        ctor.push_constraint_scope(c)

        # Return a Python action-field instance to support
        # constraints in a 'with' block
        print("__enter__: return field=%s" % str(self.field))
        return self.field
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        ctor = vsc_impl.Ctor.inst()
        
        c = ctor.pop_constraint_scope()
        ctor.pop_expr_mode()
        
        pass