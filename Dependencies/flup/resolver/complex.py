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
# $Id: complex.py 2174 2006-12-02 23:26:13Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 2174 $'

import re

from flup.resolver.resolver import *

__all__ = ['ComplexResolver']

class ComplexResolver(Resolver):
    """
    A meta-Resolver that allows you to "graft" different resolvers at various
    points in your URL space.

    It works as follows: given a PATH_INFO, it will try all matching
    resolvers, starting with the most specific. The first function returned
    by a resolver is returned as the result.

    If no matching resolvers return a function, then the search is
    considered a failure.

    Assumes that none of the registered resolvers modify environ when
    they fail to resolve.

    Upon successful resolution, SCRIPT_NAME will contain the path up to
    and including the resolved function (as determined by the resolver) and
    PATH_INFO will contain all remaining components.
    """
    _slashRE = re.compile(r'''/{2,}''')

    def __init__(self):
        self.resolverMap = {}

    def _canonicalUrl(self, url):
        if not url: # Represents default
            return url

        # Get rid of adjacent slashes
        url = self._slashRE.sub('/', url)

        # No trailing slash
        if url.endswith('/'):
            url = url[:-1]

        # Make sure it starts with a slash
        if not url.startswith('/'):
            url = '/' + url

        return url

    def addResolver(self, url, resolver):
        """
        Registers a resolver at a particular URL. The empty URL ''
        represents the default resolver. It will be matched when no
        other matching resolvers are found.
        """
        url = self._canonicalUrl(url)
        self.resolverMap[url] = resolver

    def removeResolver(self, url):
        """Removes the resolver at a particular URL."""
        url = self._canonicalUrl(url)
        del self.resolverMap[url]

    def resolve(self, request, redirect=False):
        orig_script_name = request.scriptName
        orig_path_info = path_info = request.pathInfo
        path_info = path_info.split(';')[0]
        path_info = path_info.split('/')

        assert len(path_info) > 0
        assert not path_info[0]

        while path_info:
            try_path_info = '/'.join(path_info)
            resolver = self.resolverMap.get(try_path_info)
            if resolver is not None:
                self._updatePath(request, len(path_info) - 1)
                func = resolver.resolve(request, redirect)
                if func is not None:
                    return func
                request.environ['SCRIPT_NAME'] = orig_script_name
                request.environ['PATH_INFO'] = orig_path_info
            path_info.pop()

        return None
