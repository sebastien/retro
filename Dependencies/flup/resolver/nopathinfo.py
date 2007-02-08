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
# $Id: nopathinfo.py 2174 2006-12-02 23:26:13Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 2174 $'

from flup.resolver.resolver import *

__all__ = ['NoPathInfoResolver']

class NoPathInfoResolver(Resolver):
    """
    Another meta-resolver. Disallows the existence of PATH_INFO (beyond
    what's needed to resolve the function). Optionally allows a trailing
    slash.
    """
    def __init__(self, resolver, allowTrailingSlash=False):
        self._resolver = resolver
        self._allowTrailingSlash = allowTrailingSlash

    def resolve(self, request, redirect=False):
        orig_script_name, orig_path_info = request.scriptName, request.pathInfo
        func = self._resolver.resolve(request, redirect)
        try:
            if func is not None:
                path_info = request.pathInfo.split(';')[0]
                if path_info and \
                   (not self._allowTrailingSlash or path_info != '/'):
                    func = None
            return func
        finally:
            if func is None:
                request.environ['SCRIPT_NAME'] = orig_script_name
                request.environ['PATH_INFO'] = orig_path_info
