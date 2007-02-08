# Copyright (c) 2002, 2005 Allan Saddi <allan@saddi.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# $Id: module.py 2174 2006-12-02 23:26:13Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 2174 $'

from flup.resolver.resolver import *

__all__ = ['ModuleResolver']

class NoDefault(object):
    pass

class ModuleResolver(Resolver):
    """
    Exposes all top-level callables within a module. The module's __all__
    attribute is respected, if it exists. Names beginning with underscore
    are ignored.

    Uses the first component of PATH_INFO as the callable's name and if
    empty, will instead use self.index_page.

    Upon successful resolution, appends the callable's name to SCRIPT_NAME
    and updates PATH_INFO as the remaining components of the path.

    NB: I would recommend explicitly setting the module's __all__ list.
    Otherwise, be sure all the names of module-level callables that you
    don't want exported begin with underscore.
    """
    index_page = 'index'
    
    def __init__(self, module, index=NoDefault):
        self.module = module
        if index is not NoDefault:
            self.index_page = index

    def resolve(self, request, redirect=False):
        path_info = request.pathInfo.split(';')[0]
        path_info = path_info.split('/')

        assert len(path_info) > 0
        assert not path_info[0]

        if len(path_info) < 2:
            path_info.append('')

        func_name = path_info[1]

        if func_name:
            if func_name[0] == '_' and not redirect:
                func_name = None
        else:
            func_name = self.index_page

        if func_name:
            module_all = getattr(self.module, '__all__', None)
            if module_all is None or func_name in module_all or redirect:
                func = getattr(self.module, func_name, None)
                if callable(func):
                    self._updatePath(request, 1)
                    return func
                
        return None
