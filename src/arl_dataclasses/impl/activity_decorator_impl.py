'''
Created on Mar 19, 2022

@author: mballance
'''

import typeworks
from .ctor import Ctor
from .activity_decl import ActivityDecl

class ActivityDecoratorImpl(typeworks.RegistrationDecoratorBase):

    def __init__(self, args, kwargs):
        super().__init__(ActivityDecl, args, kwargs)

    def register_decl(self, T):
        typeworks.DeclRgy.push_decl(
            ActivityDecl, 
            ActivityDecl(T),
            typeworks.enclosing_scopename(T))
