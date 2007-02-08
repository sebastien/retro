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
# $Id: resolver.py 2235 2006-12-13 16:19:23Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 2235 $'

__all__ = ['Resolver']

class Resolver(object):
    """
    Abstract base class for 'Resolver' objects. (An instance of which is
    passed to Publisher's constructor.)

    Given a Request, either return a callable (Publisher expects it to
    be a function, method, class, or callable instance), or return None.
    Typically Request.pathInfo is used to resolve the function.
    Request.environ may be modified by the Resolver, for example, to re-adjust
    SCRIPT_NAME/PATH_INFO after successful resolution. It is NOT recommended
    that it be modified if resolution fails.

    When resolving an InternalRedirect, redirect will be True.
    """
    def resolve(self, request, redirect=False):
        raise NotImplementedError, self.__class__.__name__ + '.resolve'

    def _updatePath(self, request, num):
        """
        Utility function to update SCRIPT_NAME and PATH_INFO in a sane
        manner. Transfers num components from PATH_INFO to SCRIPT_NAME.
        Keeps URL path parameters intact.
        """
        assert num >= 0
        if not num:
            return # Nothing to do
        numScriptName = len(request.scriptName.split('/'))
        totalPath = request.scriptName + request.pathInfo
        if __debug__:
            origTotalPath = totalPath
        # Extract and save params
        i = totalPath.find(';')
        if i >= 0:
            params = totalPath[i:]
            totalPath = totalPath[:i]
        else:
            params = ''
        totalPath = totalPath.split('/')
        scriptName = '/'.join(totalPath[:numScriptName + num])
        pathInfo = '/'.join([''] + totalPath[numScriptName + num:])
        # SCRIPT_NAME shouldn't have trailing slash
        if scriptName.endswith('/'):
            scriptName = scriptName[:-1]
            # Transfer to PATH_INFO (most likely empty, but just to be safe...)
            pathInfo = '/' + pathInfo
        request.environ['SCRIPT_NAME'] = scriptName
        request.environ['PATH_INFO'] = pathInfo + params
        if __debug__:
            assert request.scriptName + request.pathInfo == origTotalPath

