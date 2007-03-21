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
# $Id: gzip.py 2307 2007-01-10 18:19:00Z asaddi $

"""WSGI response gzipper middleware.

This gzip middleware component differentiates itself from others in that
it (hopefully) follows the spec more closely. Namely with regard to the
application iterator and buffering. (It doesn't buffer.) See
`Middleware Handling of Block Boundaries`_.

Of course this all comes with a price... just LOOK at this mess! :)

The inner workings of gzip and the gzip file format were gleaned from gzip.py.

.. _Middleware Handling of Block Boundaries: http://www.python.org/dev/peps/pep-0333/#middleware-handling-of-block-boundaries
"""

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 2307 $'


import struct
import time
import zlib
import re


__all__ = ['GzipMiddleware']


def _gzip_header():
    """Returns a gzip header (with no filename)."""
    # See GzipFile._write_gzip_header in gzip.py
    return '\037\213' \
           '\010' \
           '\0' + \
           struct.pack('<L', long(time.time())) + \
           '\002' \
           '\377'


class _GzipIterWrapper(object):
    """gzip application iterator wrapper.

    It ensures that: the application iterator's ``close`` method (if any) is
    called by the parent server; and at least one value is yielded each time
    the application's iterator yields a value.

    If the application's iterator yields N values, this iterator will yield
    N+1 values. This is to account for the gzip trailer.
    """

    def __init__(self, app_iter, gzip_middleware):
        self._g = gzip_middleware
        self._next = iter(app_iter).next

        self._last = False # True if app_iter has yielded last value.
        self._trailer_sent = False

        if hasattr(app_iter, 'close'):
            self.close = app_iter.close

    def __iter__(self):
        return self

    # This would've been a lot easier had I used a generator. But then I'd have
    # to wrap the generator anyway to ensure that any existing close() method
    # was called. (Calling it within the generator is not the same thing,
    # namely it does not ensure that it will be called no matter what!)
    def next(self):
        if not self._last:
            # Need to catch StopIteration here so we can append trailer.
            try:
                data = self._next()
            except StopIteration:
                self._last = True

        if not self._last:
            if self._g.gzip_ok:
                return self._g.gzip_data(data)
            else:
                return data
        else:
            # See if trailer needs to be sent.
            if self._g.header_sent and not self._trailer_sent:
                self._trailer_sent = True
                return self._g.gzip_trailer()
            # Otherwise, that's the end of this iterator.
            raise StopIteration


class _GzipMiddleware(object):
    """The actual gzip middleware component.

    Holds compression state as well implementations of ``start_response`` and
    ``write``. Instantiated before each call to the underlying application.

    This class is private. See ``GzipMiddleware`` for the public interface.
    """

    def __init__(self, start_response, mime_types, compress_level):
        self._start_response = start_response
        self._mime_types = mime_types

        self.gzip_ok = False
        self.header_sent = False

        # See GzipFile.__init__ and GzipFile._init_write in gzip.py
        self._crc = zlib.crc32('')
        self._size = 0
        self._compress = zlib.compressobj(compress_level,
                                          zlib.DEFLATED,
                                          -zlib.MAX_WBITS,
                                          zlib.DEF_MEM_LEVEL,
                                          0)

    def gzip_data(self, data):
        """Compresses the given data, prepending the gzip header if necessary.

        Returns the result as a string.
        """
        if not self.header_sent:
            self.header_sent = True
            out = _gzip_header()
        else:
            out = ''

        # See GzipFile.write in gzip.py
        length = len(data)
        if length > 0:
            self._size += length
            self._crc = zlib.crc32(data, self._crc)
            out += self._compress.compress(data)
        return out
        
    def gzip_trailer(self):
        """Returns the gzip trailer."""
        # See GzipFile.close in gzip.py
        return self._compress.flush() + \
               struct.pack('<l', self._crc) + \
               struct.pack('<L', self._size & 0xffffffffL)

    def start_response(self, status, headers, exc_info=None):
        """WSGI ``start_response`` implementation."""
        self.gzip_ok = False

        # Scan the headers. Only allow gzip compression if the Content-Type
        # is one that we're flagged to compress AND the headers do not
        # already contain Content-Encoding.
        for name,value in headers:
            name = name.lower()
            if name == 'content-type':
                value = value.split(';')[0].strip()
                for p in self._mime_types:
                    if p.match(value) is not None:
                        self.gzip_ok = True
                        break  # NB: Breaks inner loop only
            elif name == 'content-encoding':
                self.gzip_ok = False
                break

        if self.gzip_ok:
            # Remove Content-Length, if present, because compression will
            # most surely change it. (And unfortunately, we can't predict
            # the final size...)
            headers = [(name,value) for name,value in headers
                       if name.lower() != 'content-length']
            headers.append(('Content-Encoding', 'gzip'))

        _write = self._start_response(status, headers, exc_info)

        if self.gzip_ok:
            def write_gzip(data):
                _write(self.gzip_data(data))
            return write_gzip
        else:
            return _write


class GzipMiddleware(object):
    """WSGI middleware component that gzip compresses the application's
    response (if the client supports gzip compression - gleaned from the
    ``Accept-Encoding`` request header).
    """

    def __init__(self, application, mime_types=None, compress_level=9):
        """Initializes this GzipMiddleware.

        ``mime_types``
            A list of Content-Types that are OK to compress. Regular
            expressions are accepted. Defaults to ``[text/.*]`` if not
            specified.

        ``compress_level``
            The gzip compression level, an integer from 1 to 9; 1 is the
            fastest and produces the least compression, and 9 is the slowest,
            producing the most compression. The default is 9.
        """
        if mime_types is None:
            mime_types = ['text/', r'''application/(?:.+\+)?xml$''']

        self._application = application
        self._mime_types = [re.compile(m) for m in mime_types]
        self._compress_level = compress_level

    def __call__(self, environ, start_response):
        """WSGI application interface."""
        # If the client doesn't support gzip encoding, just pass through
        # directly to the application.
        if 'gzip' not in environ.get('HTTP_ACCEPT_ENCODING', ''):
            return self._application(environ, start_response)

        # All of the work is done in _GzipMiddleware and _GzipIterWrapper.
        g = _GzipMiddleware(start_response, self._mime_types,
                            self._compress_level)

        result = self._application(environ, g.start_response)

        # See if it's a length 1 iterable...
        try:
            shortcut = len(result) == 1
        except:
            shortcut = False

        if shortcut:
            # Special handling if application returns a length 1 iterable:
            # also return a length 1 iterable!
            try:
                i = iter(result)
                # Hmmm, if we get a StopIteration here, the application's
                # broken (__len__ lied!)
                data = i.next()
                if g.gzip_ok:
                    return [g.gzip_data(data) + g.gzip_trailer()]
                else:
                    return [data]
            finally:
                if hasattr(result, 'close'):
                    result.close()

        return _GzipIterWrapper(result, g)


if __name__ == '__main__':
    def app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        yield 'Hello World!\n'

    from wsgiref import validate
    app = validate.validator(app)
    app = GzipMiddleware(app)
    app = validate.validator(app)
    
    from flup.server.ajp import WSGIServer
    import logging
    WSGIServer(app, loggingLevel=logging.DEBUG).run()
