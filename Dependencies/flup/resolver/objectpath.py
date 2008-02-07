# Copyright (c) 2005 Allan Saddi <allan@saddi.com>
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
# $Id: objectpath.py 2174 2006-12-02 23:26:13Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 2174 $'

import re

from flup.resolver.resolver import *

__all__ = ['ObjectPathResolver', 'expose']

class NoDefault(object):
    pass

class ObjectPathResolver(Resolver):
    """
    Inspired by CherryPy <http://www.cherrypy.org/>. :) For an explanation
    of how this works, see the excellent tutorial at
    <http://www.cherrypy.org/wiki/CherryPyTutorial>. We support the index and
    default methods, though the calling convention for the default method
    is different - we do not pass PATH_INFO as positional arguments. (It
    is passed through the request/environ as normal.)

    Also, we explicitly block certain function names. See below. I don't
    know if theres really any harm in letting those attributes be followed,
    but I'd rather not take the chance. And unfortunately, this solution
    is pretty half-baked as well (I'd rather only allow certain object
    types to be traversed, rather than disallow based on names.) Better
    than nothing though...
    """
    index_page = 'index'
    default_page = 'default'

    def __init__(self, root, index=NoDefault, default=NoDefault,
                 favorIndex=True):
        """
        root is the root object of your URL hierarchy. In CherryPy, this
        would be cpg.root.

        When the last component of a path has an index method and some
        object along the path has a default method, favorIndex determines
        which method is called when the URL has a trailing slash. If
        True, the index method will be called. Otherwise, the default method.
        """
        self.root = root
        if index is not NoDefault:
            self.index_page = index
        if default is not NoDefault:
            self.default_page = default
        self._favorIndex = favorIndex

    # Certain names should be disallowed for safety. If one of your pages
    # is showing up unexpectedly as a 404, make sure the function name doesn't
    # begin with one of these prefixes.
    _disallowed = re.compile(r'''(?:_|im_|func_|tb_|f_|co_).*''')

    def _exposed(self, obj, redirect):
        # If redirecting, allow non-exposed objects as well.
        return callable(obj) and (getattr(obj, 'exposed', False) or redirect)

    def resolve(self, request, redirect=False):
        path_info = request.pathInfo.split(';')[0]
        path_info = path_info.split('/')

        assert len(path_info) > 0
        assert not path_info[0]

        current = self.root
        current_default = None
        i = 0
        for i in range(1, len(path_info)):
            component = path_info[i]

            # See if we have an index page (needed for index/default
            # disambiguation, unfortunately).
            current_index = None
            if self.index_page:
                current_index = getattr(current, self.index_page, None)
                if not self._exposed(current_index, redirect):
                    current_index = None

            if self.default_page:
                # Remember the last default page we've seen.
                new_default = getattr(current, self.default_page, None)
                if self._exposed(new_default, redirect):
                    current_default = (i - 1, new_default)

            # Test for trailing slash.
            if not component and current_index is not None and \
               (self._favorIndex or current_default is None):
                # Breaking out of the loop here favors index over default.
                break

            # Respect __all__ attribute. (Ok to generalize to all objects?)
            all = getattr(current, '__all__', None)

            current = getattr(current, component, None)
            # Path doesn't exist
            if current is None or self._disallowed.match(component) or \
               (all is not None and component not in all and not redirect):
                # Use path up to latest default page.
                if current_default is not None:
                    i, current = current_default
                    break
                # No default at all, so we fail.
                return None

        func = None
        if self._exposed(current, redirect): # Exposed?
            func = current
        else:
            # If not, see if it as an exposed index page
            if self.index_page:
                index = getattr(current, self.index_page, None)
                if self._exposed(index, redirect): func = index
            # How about a default page?
            if func is None and self.default_page:
                default = getattr(current, self.default_page, None)
                if self._exposed(default, redirect): func = default
            # Lastly, see if we have an ancestor's default page to fall back on.
            if func is None and current_default is not None:
                i, func = current_default

        if func is not None:
            self._updatePath(request, i)

        return func

def expose(func):
    """Decorator to expose functions."""
    func.exposed = True
    return func
