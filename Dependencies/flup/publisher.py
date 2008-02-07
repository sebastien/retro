# Copyright (c) 2002, 2005, 2006 Allan Saddi <allan@saddi.com>
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
# $Id: publisher.py 1853 2006-04-06 23:05:58Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 1853 $'

import os
import inspect
import cgi
import types
from Cookie import SimpleCookie

__all__ = ['Request',
           'Response',
           'Transaction',
           'Publisher',
           'File',
           'Action',
           'Redirect',
           'InternalRedirect',
           'getexpected',
           'trimkw']

class NoDefault(object):
    """Sentinel object so we can distinguish None in keyword arguments."""
    pass

class Request(object):
    """
    Encapsulates data about the HTTP request.

    Supported attributes that originate from here: (The attributes are
    read-only, however you may modify the contents of environ.)
      transaction - Enclosing Transaction object.
      environ - Environment variables, as passed from WSGI adapter.
      method - Request method.
      publisherScriptName - SCRIPT_NAME of Publisher.
      scriptName - SCRIPT_NAME for request.
      pathInfo - PATH_INFO for request.
      form - Dictionary containing data from query string and/or POST request.
      cookie - Cookie from request.
    """
    def __init__(self, transaction, environ):
        self._transaction = transaction

        self._environ = environ
        self._publisherScriptName = environ.get('SCRIPT_NAME', '')

        self._form = {}
        self._parseFormData()

        # Is this safe? Will it ever raise exceptions?
        self._cookie = SimpleCookie(environ.get('HTTP_COOKIE', None))

    def _parseFormData(self):
        """
        Fills self._form with data from a FieldStorage. May be overidden to
        provide custom form processing. (Like no processing at all!)
        """
        # Parse query string and/or POST data.
        form = FieldStorage(fp=self._environ['wsgi.input'],
                            environ=self._environ, keep_blank_values=1)

        # Collapse FieldStorage into a simple dict.
        if form.list is not None:
            for field in form.list:
                # Wrap uploaded files
                if field.filename:
                    val = File(field)
                else:
                    val = field.value

                # Add File/value to args, constructing a list if there are
                # multiple values.
                if self._form.has_key(field.name):
                    self._form[field.name].append(val)
                else:
                    self._form[field.name] = [val]

        # Unwrap lists with a single item.
        for name,val in self._form.items():
            if len(val) == 1:
                self._form[name] = val[0]

    def _get_transaction(self):
        return self._transaction
    transaction = property(_get_transaction, None, None,
                           "Transaction associated with this Request")
    
    def _get_environ(self):
        return self._environ
    environ = property(_get_environ, None, None,
                       "Environment variables passed from adapter")
    
    def _get_method(self):
        return self._environ['REQUEST_METHOD']
    method = property(_get_method, None, None,
                      "Request method")
    
    def _get_publisherScriptName(self):
        return self._publisherScriptName
    publisherScriptName = property(_get_publisherScriptName, None, None,
                                   'SCRIPT_NAME of Publisher')

    def _get_scriptName(self):
        return self._environ.get('SCRIPT_NAME', '')
    scriptName = property(_get_scriptName, None, None,
                        "SCRIPT_NAME of request")

    def _get_pathInfo(self):
        return self._environ.get('PATH_INFO', '')
    pathInfo = property(_get_pathInfo, None, None,
                        "PATH_INFO of request")

    def _get_form(self):
        return self._form
    form = property(_get_form, None, None,
                    "Parsed GET/POST data")

    def _get_cookie(self):
        return self._cookie
    cookie = property(_get_cookie, None, None,
                      "Cookie received from client")

class Response(object):
    """
    Encapsulates response-related data.

    Supported attributes:
      transaction - Enclosing Transaction object.
      status - Response status code (and message).
      headers - Response headers.
      cookie - Response cookie.
      contentType - Content type of body.
      body - Response body. Must be an iterable that yields strings.

    Since there are multiple ways of passing response info back to
    Publisher, here is their defined precedence:
      status - headers['Status'] first, then status
      cookie - Any values set in this cookie are added to the headers in
        addition to existing Set-Cookie headers.
      contentType - headers['Content-Type'] first, then contentType. If
        neither are specified, defaults to 'text/html'.
      body - Return of function takes precedence. If function returns None,
        body is used instead.
    """
    _initialHeaders = {
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
        }

    def __init__(self, transaction):
        self._transaction = transaction

        self._status = '200 OK'

        # Initial response headers.
        self._headers = header_dict(self._initialHeaders)

        self._cookie = SimpleCookie()

        self.body = []

    def _get_transaction(self):
        return self._transaction
    transaction = property(_get_transaction, None, None,
                           "Transaction associated with this Response")
    
    def _get_status(self):
        status = self._headers.get('Status')
        if status is not None:
            return status
        return self._status
    def _set_status(self, value):
        if self._headers.has_key('Status'):
            self._headers['Status'] = value
        else:
            self._status = value
    status = property(_get_status, _set_status, None,
                      'Response status')

    def _get_headers(self):
        return self._headers
    headers = property(_get_headers, None, None,
                       "Headers to send in response")

    def _get_cookie(self):
        return self._cookie
    cookie = property(_get_cookie, None, None,
                      "Cookie to send in response")

    def _get_contentType(self):
        return self._headers.get('Content-Type', 'text/html')
    def _set_contentType(self, value):
        self._headers['Content-Type'] = value
    contentType = property(_get_contentType, _set_contentType, None,
                           'Content-Type of the response body')

class Transaction(object):
    """
    Encapsulates objects associated with a single transaction (Request,
    Response, and possibly a Session).

    Public attributes: (all read-only)
      request - Request object.
      response - Response object.

    If Publisher sits on top of SessionMiddleware, the public API of
    SessionService is also available through the Transaction object.
    """
    _requestClass = Request
    _responseClass = Response

    def __init__(self, publisher, environ):
        self._publisher = publisher
        self._request = self._requestClass(self, environ)
        self._response = self._responseClass(self)

        # Session support.
        self._sessionService = environ.get('com.saddi.service.session')
        if self._sessionService is not None:
            self.encodeURL = self._sessionService.encodeURL

    def _get_request(self):
        return self._request
    request = property(_get_request, None, None,
                       "Request associated with this Transaction")

    def _get_response(self):
        return self._response
    response = property(_get_response, None, None,
                        "Response associated with this Transaction")

    # Export SessionService API

    def _get_session(self):
        assert self._sessionService is not None, 'No session service found'
        return self._sessionService.session
    session = property(_get_session, None, None,
                       'Returns the Session object associated with this '
                       'client')

    def _get_hasSession(self):
        assert self._sessionService is not None, 'No session service found'
        return self._sessionService.hasSession
    hasSession = property(_get_hasSession, None, None,
                          'True if a Session currently exists for this client')

    def _get_isSessionNew(self):
        assert self._sessionService is not None, 'No session service found'
        return self._sessionService.isSessionNew
    isSessionNew = property(_get_isSessionNew, None, None,
                            'True if the Session was created in this '
                            'transaction')

    def _get_hasSessionExpired(self):
        assert self._sessionService is not None, 'No session service found'
        return self._sessionService.hasSessionExpired
    hasSessionExpired = property(_get_hasSessionExpired, None, None,
                                 'True if the client was associated with a '
                                 'non-existent Session')

    def _get_encodesSessionInURL(self):
        assert self._sessionService is not None, 'No session service found'
        return self._sessionService.encodesSessionInURL
    def _set_encodesSessionInURL(self, value):
        assert self._sessionService is not None, 'No session service found'
        self._sessionService.encodesSessionInURL = value
    encodesSessionInURL = property(_get_encodesSessionInURL,
                                   _set_encodesSessionInURL, None,
                                   'True if the Session ID should be encoded '
                                   'in the URL')

    def prepare(self):
        """
        Called before resolved function is invoked. If overridden,
        super's prepare() MUST be called and it must be called first.
        """
        # Pass form values as keyword arguments.
        args = dict(self._request.form)

        # Pass Transaction to function if it wants it.
        args['transaction'] = args['trans'] = self

        self._args = args

    def call(self, func, args):
        """
        May be overridden to provide custom exception handling and/or
        per-request additions, e.g. opening a database connection,
        starting a transaction, etc.
        """
        # Trim down keywords to only what the callable expects.
        expected, varkw = getexpected(func)
        trimkw(args, expected, varkw)

        return func(**args)

    def run(self, func):
        """
        Execute the function, doing any Action processing and also
        post-processing the function/Action's return value.
        """
        try:
            # Call the function.
            result = self.call(func, self._args)
        except Action, a:
            # Caught an Action, have it do whatever it does
            result = a.run(self)

        response = self._response
        headers = response.headers

        if result is not None:
            if type(result) in types.StringTypes:
                assert type(result) is str, 'result cannot be unicode!'

                # Set Content-Length, if needed
                if not headers.has_key('Content-Length'):
                    headers['Content-Length'] = str(len(result))

                # Wrap in list for WSGI
                response.body = [result]
            else:
                if __debug__:
                    try:
                        iter(result)
                    except TypeError:
                        raise AssertionError, 'result not iterable!'
                response.body = result

        # If result was None, assume response.body was appropriately set.

    def finish(self):
        """
        Called after resolved function returns, but before response is
        sent. If overridden, super's finish() should be called last.
        """
        response = self._response
        headers = response.headers

        # Copy cookie to headers.
        items = response.cookie.items()
        items.sort()
        for name,morsel in items:
            headers.add('Set-Cookie', morsel.OutputString())

        # If there is a Status header, transfer its value to response.status.
        # It must not remain in the headers!
        status = headers.get('Status', NoDefault)
        if status is not NoDefault:
            del headers['Status']
            response.status = status

        code = int(response.status[:3])
        # Check if it's a response that must not include a body.
        # (See 4.3 in RFC2068.)
        if code / 100 == 1 or code in (204, 304):
            # Remove any trace of the response body, if that's the case.
            for header,value in headers.items():
                if header.lower().startswith('content-'):
                    del headers[header]
            response.body = []
        else:
            if self._request.method == 'HEAD':
                # HEAD reponse must not return a body (but the headers must be
                # kept intact).
                response.body = []

            # Add Content-Type, if missing.
            if not headers.has_key('Content-Type'):
                headers['Content-Type'] = response.contentType

        # If we have a close() method, ensure that it is called.
        if hasattr(self, 'close'):
            response.body = _addClose(response.body, self.close)

class Publisher(object):
    """
    WSGI application that publishes Python functions as web pages. Constructor
    takes an instance of a concrete subclass of Resolver, which is responsible
    for mapping requests to functions.

    Query string/POST data values are passed to the function as keyword
    arguments. If the function does not support variable keywords (e.g.
    does not have a ** parameter), the function will only be passed
    keywords which it expects. It is recommended that all keyword parameters
    have defaults so that missing form data does not raise an exception.

    A Transaction instance is always passed to the function via the
    "transaction" or "trans" keywords. See the Transaction, Request, and
    Response classes.

    Valid return types for the function are: a string, None, or an iterable
    that yields strings. If returning None, it is expected that Response.body
    has been appropriately set. (It must be an iterable that yields strings.)

    An instance of Publisher itself is the WSGI application.
    """
    _transactionClass = Transaction

    def __init__(self, resolver, transactionClass=None, error404=None):
        self._resolver = resolver

        if transactionClass is not None:
            self._transactionClass = transactionClass

        if error404 is not None:
            self._error404 = error404

    def _get_resolver(self):
        return self._resolver
    resolver = property(_get_resolver, None, None,
                        'Associated Resolver for this Publisher')

    def __call__(self, environ, start_response):
        """
        WSGI application interface. Creates a Transaction (which does most
        of the work) and sends the response.
        """
        # Set up a Transaction.
        transaction = self._transactionClass(self, environ)

        # Make any needed preparations.
        transaction.prepare()

        redirect = False

        while True:
            # Attempt to resolve the function.
            func = self._resolver.resolve(transaction.request,
                                          redirect=redirect)
            if func is None:
                func = self._error404

            try:
                # Call the function.
                transaction.run(func)
            except InternalRedirect, r:
                # Internal redirect. Set up environment and resolve again.
                environ['SCRIPT_NAME'] = transaction.request.publisherScriptName
                environ['PATH_INFO'] = r.pathInfo
                redirect = True
            else:
                break

        # Give Transaction a chance to do modify/add to the response.
        transaction.finish()

        # Transform headers into a list. (Need to pay attention to
        # multiple values.)
        responseHeaders = []
        for key,value in transaction.response.headers.items():
            if type(value) is list:
                for v in value:
                    responseHeaders.append((key, v))
            else:
                responseHeaders.append((key, value))

        start_response(transaction.response.status, responseHeaders)
        return transaction.response.body

    def _error404(self, transaction):
        """Error page to display when resolver fails."""
        transaction.response.status = '404 Not Found'
        request_uri = transaction.request.environ.get('REQUEST_URI')
        if request_uri is None:
            request_uri = transaction.request.environ.get('SCRIPT_NAME', '') + \
                          transaction.request.environ.get('PATH_INFO', '')
        return ["""<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>404 Not Found</title>
</head><body>
<h1>Not Found</h1>
The requested URL %s was not found on this server.<p>
<hr>
%s</body></html>
""" % (request_uri, transaction.request.environ.get('SERVER_SIGNATURE', ''))]

class File(object):
    """
    Wrapper so we can identify uploaded files.
    """
    def __init__(self, field):
        self.filename = field.filename
        self.file = field.file
        self.type = field.type
        self.type_options = field.type_options
        self.headers = field.headers
        
class Action(Exception):
    """
    Abstract base class for 'Actions', which are just exceptions.
    Within Publisher, Actions have no inherent meaning and are used
    as a shortcut to perform specific actions where it's ok for a
    function to abruptly halt. (Like redirects or displaying an
    error page.)

    I don't know if using exceptions this way is good form (something
    tells me no ;) Their usage isn't really required, but they're
    convenient in some situations.
    """
    def run(self, transaction):
        """Override to perform your action."""
        raise NotImplementedError, self.__class__.__name__ + '.run'

class Redirect(Action):
    """
    Redirect to the given URL.
    """
    def __init__(self, url, permanent=False):
        self._url = url
        self._permanent = permanent

    def run(self, transaction):
        response = transaction.response
        response.status = self._permanent and '301 Moved Permanently' or \
                          '302 Moved Temporarily'
        response.headers.reset()
        response.headers['Location'] = self._url
        response.contentType = 'text/html'
        return ["""<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>%s</title>
</head><body>
<h1>Found</h1>
<p>The document has moved <a href="%s">here</a>.</p>
<hr>
%s</body></html>
""" % (response.status, self._url,
       transaction.request.environ.get('SERVER_SIGNATURE', ''))]

class InternalRedirect(Exception):
    """
    An internal redirect using a new PATH_INFO (relative to Publisher's
    SCRIPT_NAME).

    When handling an InternalRedirect, the behavior of all included
    Resolvers is to expose a larger set of callables (that would normally
    be hidden). Therefore, it is important that you set pathInfo securely -
    preferably, it should not depend on any data from the request. Ideally,
    pathInfo should be a constant string.
    """
    def __init__(self, pathInfo):
        self.pathInfo = pathInfo

class FieldStorage(cgi.FieldStorage):
    def __init__(self, *args, **kw):
        """
        cgi.FieldStorage only parses the query string during a GET or HEAD
        request. Fix this.
        """
        cgi.FieldStorage.__init__(self, *args, **kw)

        environ = kw.get('environ') or os.environ
        method = environ.get('REQUEST_METHOD', 'GET').upper()
        if method not in ('GET', 'HEAD'): # cgi.FieldStorage already parsed?
            qs = environ.get('QUERY_STRING')
            if qs:
                if self.list is None:
                    self.list = []
                for key,value in cgi.parse_qsl(qs, self.keep_blank_values,
                                               self.strict_parsing):
                    self.list.append(cgi.MiniFieldStorage(key, value))

class header_dict(dict):
    """
    This is essentially a case-insensitive dictionary, with some additions
    geared towards supporting HTTP headers (like __str__(), add(), and
    reset()).
    """
    def __init__(self, val=None):
        """
        If initialized with an existing dictionary, calling reset() will
        reset our contents back to that initial dictionary.
        """
        dict.__init__(self)
        self._keymap = {}
        if val is None:
            val = {}
        self.update(val)
        self._reset_state = dict(val)
        
    def __contains__(self, key):
        return key.lower() in self._keymap

    def __delitem__(self, key):
        lower_key = key.lower()
        real_key = self._keymap.get(lower_key)
        if real_key is None:
            raise KeyError, key
        del self._keymap[lower_key]
        dict.__delitem__(self, real_key)

    def __getitem__(self, key):
        lower_key = key.lower()
        real_key = self._keymap.get(lower_key)
        if real_key is None:
            raise KeyError, key
        return dict.__getitem__(self, real_key)

    def __str__(self):
        """Output as HTTP headers."""
        s = ''
        for k,v in self.items():
            if type(v) is list:
                for i in v:
                    s += '%s: %s\n' % (k, i)
            else:
                s += '%s: %s\n' % (k, v)
        return s
    
    def __setitem__(self, key, value):
        lower_key = key.lower()
        real_key = self._keymap.get(lower_key)
        if real_key is None:
            self._keymap[lower_key] = key
            dict.__setitem__(self, key, value)
        else:
            dict.__setitem__(self, real_key, value)

    def clear(self):
        self._keymap.clear()
        dict.clear(self)

    def copy(self):
        c = self.__class__(self)
        c._reset_state = self._reset_state
        return c

    def get(self, key, failobj=None):
        lower_key = key.lower()
        real_key = self._keymap.get(lower_key)
        if real_key is None:
            return failobj
        return dict.__getitem__(self, real_key)
    
    def has_key(self, key):
        return key.lower() in self._keymap

    def setdefault(self, key, failobj=None):
        lower_key = key.lower()
        real_key = self._keymap.get(lower_key)
        if real_key is None:
            self._keymap[lower_key] = key
            dict.__setitem__(self, key, failobj)
            return failobj
        else:
            return dict.__getitem__(self, real_key)
        
    def update(self, d):
        for k,v in d.items():
            self[k] = v
            
    def add(self, key, value):
        """
        Add a new header value. Does not overwrite previous value of header
        (in contrast to __setitem__()).
        """
        if self.has_key(key):
            if type(self[key]) is list:
                self[key].append(value)
            else:
                self[key] = [self[key], value]
        else:
            self[key] = value

    def reset(self):
        """Reset contents to that at the time this instance was created."""
        self.clear()
        self.update(self._reset_state)

def _addClose(appIter, closeFunc):
    """
    Wraps an iterator so that its close() method calls closeFunc. Respects
    the existence of __len__ and the iterator's own close() method.

    Need to use metaclass magic because __len__ and next are not
    recognized unless they're part of the class. (Can't assign at
    __init__ time.)
    """
    class metaIterWrapper(type):
        def __init__(cls, name, bases, clsdict):
            super(metaIterWrapper, cls).__init__(name, bases, clsdict)
            if hasattr(appIter, '__len__'):
                cls.__len__ = appIter.__len__
            cls.next = iter(appIter).next
            if hasattr(appIter, 'close'):
                def _close(self):
                    appIter.close()
                    closeFunc()
                cls.close = _close
            else:
                cls.close = closeFunc

    class iterWrapper(object):
        __metaclass__ = metaIterWrapper
        def __iter__(self):
            return self

    return iterWrapper()

# Utilities which may be useful outside of Publisher? Perhaps for decorators...

def getexpected(func):
    """
    Returns as a 2-tuple the passed in object's expected arguments and
    whether or not it accepts variable keywords.
    """
    assert callable(func), 'object not callable'

    if not inspect.isclass(func):
        # At this point, we assume func is either a function, method, or
        # callable instance.
        if not inspect.isfunction(func) and not inspect.ismethod(func):
            func = getattr(func, '__call__') # When would this fail?

        argspec = inspect.getargspec(func)
        expected, varkw = argspec[0], argspec[2] is not None
        if inspect.ismethod(func):
            expected = expected[1:]
    else:
        # A class. Try to figure out the calling conventions of the
        # constructor.
        init = getattr(func, '__init__', None)
        # Sigh, this is getting into the realm of black magic...
        if init is not None and inspect.ismethod(init):
            argspec = inspect.getargspec(init)
            expected, varkw = argspec[0], argspec[2] is not None
            expected = expected[1:]
        else:
            expected, varkw = [], False

    return expected, varkw

def trimkw(kw, expected, varkw):
    """
    If necessary, trims down a dictionary of keyword arguments to only
    what's expected.
    """
    if not varkw: # Trimming only necessary if it doesn't accept variable kw
        for name in kw.keys():
            if name not in expected:
                del kw[name]
