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
# $Id: importingmodule.py 2174 2006-12-02 23:26:13Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 2174 $'

import sys
import os
import imp

from flup.resolver.resolver import *

__all__ = ['ImportingModuleResolver']

class NoDefault(object):
    pass

class ImportingModuleResolver(Resolver):
    """
    Constructor takes a directory name or a list of directories. Interprets
    the first two components of PATH_INFO as 'module/function'. Modules
    are imported as needed and must reside in the directories specified.
    Module and function names beginning with underscore are ignored.

    If the 'module' part of PATH_INFO is missing, it is assumed to be
    self.default_module.

    If the 'function' part of PATH_INFO is missing, it is assumed to be
    self.index_page.

    Upon successful resolution, appends the module and function names to
    SCRIPT_NAME and updates PATH_INFO as the remaining components of the path.

    NB: I would recommend explicitly setting all modules' __all__ list.
    Otherwise, be sure all the names of module-level callables that you
    don't want exported begin with underscore.
    """
    # No default module by default.
    default_module = None
    index_page = 'index'

    def __init__(self, path, defaultModule=NoDefault, index=NoDefault):
        self.path = path
        if defaultModule is not NoDefault:
            self.default_module = defaultModule
        if index is not NoDefault:
            self.index_page = index

    def resolve(self, request, redirect=False):
        path_info = request.pathInfo.split(';')[0]
        path_info = path_info.split('/')

        assert len(path_info) > 0
        assert not path_info[0]

        while len(path_info) < 3:
            path_info.append('')

        module_name, func_name = path_info[1:3]

        if not module_name:
            module_name = self.default_module

        if not func_name:
            func_name = self.index_page

        module = None
        if module_name and (module_name[0] != '_' or redirect) and \
           not module_name.count('.'):
            module = _import_module(module_name, path=self.path)

        if module is not None:
            if func_name and (func_name[0] != '_' or redirect):
                module_all = getattr(module, '__all__', None)
                if module_all is None or func_name in module_all or redirect:
                    func = getattr(module, func_name, None)
                    if callable(func):
                        self._updatePath(request, 2)
                        return func

        return None

def _import_module(name, path=None):
    """
    Imports a module. If path is None, module will be searched for in
    sys.path. If path is given (which may be a single string or a list),
    the module will only be searched for in those directories.
    """
    if path is not None and type(path) is not list:
        path = [path]

    module = sys.modules.get(name)
    if module is not None:
        module_file = getattr(module, '__file__')
        if module_file is None or \
               (path is not None and os.path.dirname(module_file) not in path):
            return None

        return module

    fp, pathname, description = imp.find_module(name, path)
    try:
        return imp.load_module(name, fp, pathname, description)
    finally:
        if fp:
            fp.close()
