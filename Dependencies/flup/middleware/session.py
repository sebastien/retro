# Copyright (c) 2005, 2006 Allan Saddi <allan@saddi.com>
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
# $Id: session.py 2236 2006-12-13 16:24:15Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 2236 $'

import os
import errno
import string
import time
import weakref
import atexit
import shelve
import cPickle as pickle

try:
    import threading
except ImportError:
    import dummy_threading as threading

__all__ = ['Session',
           'SessionStore',
           'MemorySessionStore',
           'ShelveSessionStore',
           'DiskSessionStore',
           'SessionMiddleware']

class Session(dict):
    """
    Session objects, basically dictionaries.
    """
    identifierLength = 32
    # Would be nice if len(identifierChars) were some power of 2.
    identifierChars = string.digits + string.ascii_letters + '-_'

    def __init__(self, identifier):
        super(Session, self).__init__()

        assert self.isIdentifierValid(identifier)
        self._identifier = identifier

        self._creationTime = self._lastAccessTime = time.time()
        self._isValid = True

    def _get_identifier(self):
        return self._identifier
    identifier = property(_get_identifier, None, None,
                          'Unique identifier for Session within its Store')

    def _get_creationTime(self):
        return self._creationTime
    creationTime = property(_get_creationTime, None, None,
                            'Time when Session was created')

    def _get_lastAccessTime(self):
        return self._lastAccessTime
    lastAccessTime = property(_get_lastAccessTime, None, None,
                              'Time when Session was last accessed')

    def _get_isValid(self):
        return self._isValid
    isValid = property(_get_isValid, None, None,
                       'Whether or not this Session is valid')

    def touch(self):
        """Update Session's access time."""
        self._lastAccessTime = time.time()

    def invalidate(self):
        """Invalidate this Session."""
        self.clear()
        self._creationTime = self._lastAccessTime = 0
        self._isValid = False

    def isIdentifierValid(cls, ident):
        """
        Returns whether or not the given string *could be* a valid session
        identifier.
        """
        if type(ident) is str and len(ident) == cls.identifierLength:
            for c in ident:
                if c not in cls.identifierChars:
                    return False
            return True
        return False
    isIdentifierValid = classmethod(isIdentifierValid)

    def generateIdentifier(cls):
        """
        Generate a random session identifier.
        """
        raw = os.urandom(cls.identifierLength)

        sessId = ''
        for c in raw:
            # So we lose 2 bits per random byte...
            sessId += cls.identifierChars[ord(c) % len(cls.identifierChars)]
        return sessId
    generateIdentifier = classmethod(generateIdentifier)

def _shutdown(ref):
    store = ref()
    if store is not None:
        store.shutdown()

class SessionStore(object):
    """
    Abstract base class for session stores. You first acquire a session by
    calling createSession() or checkOutSession(). After using the session,
    you must call checkInSession(). You must not keep references to sessions
    outside of a check in/check out block. Always obtain a fresh reference.

    Some external mechanism must be set up to call periodic() periodically
    (perhaps every 5 minutes).

    After timeout minutes of inactivity, sessions are deleted.
    """
    _sessionClass = Session

    def __init__(self, timeout=60, sessionClass=None):
        self._lock = threading.Condition()

        # Timeout in minutes
        self._sessionTimeout = timeout

        if sessionClass is not None:
            self._sessionClass = sessionClass

        self._checkOutList = {}
        self._shutdownRan = False

        # Ensure shutdown is called.
        atexit.register(_shutdown, weakref.ref(self))

    # Public interface.

    def createSession(self):
        """
        Create a new session with a unique identifier. Should never fail.
        (Will raise a RuntimeError in the rare event that it does.)

        The newly-created session should eventually be released by
        a call to checkInSession().
        """
        assert not self._shutdownRan
        self._lock.acquire()
        try:
            attempts = 0
            while attempts < 10000:
                sessId = self._sessionClass.generateIdentifier()
                sess = self._createSession(sessId)
                if sess is not None: break
                attempts += 1

            if attempts >= 10000:
                raise RuntimeError, self.__class__.__name__ + \
                      '.createSession() failed'

            assert sess.identifier not in self._checkOutList
            self._checkOutList[sess.identifier] = sess
            return sess
        finally:
            self._lock.release()

    def checkOutSession(self, identifier):
        """
        Checks out a session for use. Returns the session if it exists,
        otherwise returns None. If this call succeeds, the session
        will be touch()'ed and locked from use by other processes.
        Therefore, it should eventually be released by a call to
        checkInSession().
        """
        assert not self._shutdownRan

        if not self._sessionClass.isIdentifierValid(identifier):
            return None

        self._lock.acquire()
        try:
            # If we know it's already checked out, block.
            while identifier in self._checkOutList:
                self._lock.wait()
            sess = self._loadSession(identifier)
            if sess is not None:
                if sess.isValid:
                    assert sess.identifier not in self._checkOutList
                    self._checkOutList[sess.identifier] = sess
                    sess.touch()
                else:
                    # No longer valid (same as not existing). Delete/unlock
                    # the session.
                    self._deleteSession(sess.identifier)
                    sess = None
            return sess
        finally:
            self._lock.release()

    def checkInSession(self, session):
        """
        Returns the session for use by other threads/processes. Safe to
        pass None.
        """
        assert not self._shutdownRan

        if session is None:
            return

        self._lock.acquire()
        try:
            assert session.identifier in self._checkOutList
            if session.isValid:
                self._saveSession(session)
            else:
                self._deleteSession(session.identifier)
            del self._checkOutList[session.identifier]
            self._lock.notify()
        finally:
            self._lock.release()

    def shutdown(self):
        """Clean up outstanding sessions."""
        self._lock.acquire()
        try:
            if not self._shutdownRan:
                # Save or delete any sessions that are still out there.
                for key,sess in self._checkOutList.items():
                    if sess.isValid:
                        self._saveSession(sess)
                    else:
                        self._deleteSession(sess.identifier)
                self._checkOutList.clear()
                self._shutdown()
                self._shutdownRan = True
        finally:
            self._lock.release()

    def __del__(self):
        self.shutdown()

    def periodic(self):
        """Timeout old sessions. Should be called periodically."""
        self._lock.acquire()
        try:
            if not self._shutdownRan:
                self._periodic()
        finally:
            self._lock.release()

    # To be implemented by subclasses. self._lock will be held whenever
    # these are called and for methods that take an identifier,
    # the identifier will be guaranteed to be valid (but it will not
    # necessarily exist).

    def _createSession(self, identifier):
        """
        Attempt to create the session with the given identifier. If
        successful, return the newly-created session, which must
        also be implicitly locked from use by other processes. (The
        session returned should be an instance of self._sessionClass.)
        If unsuccessful, return None.
        """
        raise NotImplementedError, self.__class__.__name__ + '._createSession'
        
    def _loadSession(self, identifier):
        """
        Load the session with the identifier from secondary storage returning
        None if it does not exist. If the load is successful, the session
        must be locked from use by other processes.
        """
        raise NotImplementedError, self.__class__.__name__ + '._loadSession'

    def _saveSession(self, session):
        """
        Store the session into secondary storage. Also implicitly releases
        the session for use by other processes.
        """
        raise NotImplementedError, self.__class__.__name__ + '._saveSession'

    def _deleteSession(self, identifier):
        """
        Deletes the session from secondary storage. Must be OK to pass
        in an invalid (non-existant) identifier. If the session did exist,
        it must be released for use by other processes.
        """
        raise NotImplementedError, self.__class__.__name__ + '._deleteSession'

    def _periodic(self):
        """Remove timedout sessions from secondary storage."""
        raise NotImplementedError, self.__class__.__name__ + '._periodic'
        
    def _shutdown(self):
        """Performs necessary shutdown actions for secondary store."""
        raise NotImplementedError, self.__class__.__name__ + '._shutdown'

    # Utilities

    def _isSessionTimedout(self, session, now=time.time()):
        return (session.lastAccessTime + self._sessionTimeout * 60) < now
    
class MemorySessionStore(SessionStore):
    """
    Memory-based session store. Great for persistent applications, terrible
    for one-shot ones. :)
    """
    def __init__(self, *a, **kw):
        super(MemorySessionStore, self).__init__(*a, **kw)

        # Our "secondary store".
        self._secondaryStore = {}

    def _createSession(self, identifier):
        if self._secondaryStore.has_key(identifier):
            return None
        sess = self._sessionClass(identifier)
        self._secondaryStore[sess.identifier] = sess
        return sess

    def _loadSession(self, identifier):
        return self._secondaryStore.get(identifier, None)

    def _saveSession(self, session):
        self._secondaryStore[session.identifier] = session

    def _deleteSession(self, identifier):
        if self._secondaryStore.has_key(identifier):
            del self._secondaryStore[identifier]

    def _periodic(self):
        now = time.time()
        for key,sess in self._secondaryStore.items():
            if self._isSessionTimedout(sess, now):
                del self._secondaryStore[key]
        
    def _shutdown(self):
        pass

class ShelveSessionStore(SessionStore):
    """
    Session store based on Python "shelves." Only use if you can guarantee
    that storeFile will NOT be accessed concurrently by other instances.
    (In other processes, threads, anywhere!)
    """
    def __init__(self, storeFile='sessions', *a, **kw):
        super(ShelveSessionStore, self).__init__(*a, **kw)

        self._secondaryStore = shelve.open(storeFile,
                                           protocol=pickle.HIGHEST_PROTOCOL)

    def _createSession(self, identifier):
        if self._secondaryStore.has_key(identifier):
            return None
        sess = self._sessionClass(identifier)
        self._secondaryStore[sess.identifier] = sess
        return sess

    def _loadSession(self, identifier):
        return self._secondaryStore.get(identifier, None)

    def _saveSession(self, session):
        self._secondaryStore[session.identifier] = session

    def _deleteSession(self, identifier):
        if self._secondaryStore.has_key(identifier):
            del self._secondaryStore[identifier]

    def _periodic(self):
        now = time.time()
        for key,sess in self._secondaryStore.items():
            if self._isSessionTimedout(sess, now):
                del self._secondaryStore[key]
        
    def _shutdown(self):
        self._secondaryStore.close()

class DiskSessionStore(SessionStore):
    """
    Disk-based session store that stores each session as its own file
    within a specified directory. Should be safe for concurrent use.
    (As long as the underlying OS/filesystem respects create()'s O_EXCL.)
    """
    def __init__(self, storeDir='sessions', *a, **kw):
        super(DiskSessionStore, self).__init__(*a, **kw)

        self._sessionDir = storeDir
        if not os.access(self._sessionDir, os.F_OK):
            # Doesn't exist, try to create it.
            os.mkdir(self._sessionDir)

    def _filenameForSession(self, identifier):
        return os.path.join(self._sessionDir, identifier + '.sess')

    def _lockSession(self, identifier, block=True):
        # Release SessionStore lock so we don't deadlock.
        self._lock.release()
        try:
            fn = self._filenameForSession(identifier) + '.lock'
            while True:
                try:
                    fd = os.open(fn, os.O_WRONLY|os.O_CREAT|os.O_EXCL)
                except OSError, e:
                    if e.errno != errno.EEXIST:
                        raise
                else:
                    os.close(fd)
                    break

                if not block:
                    return False

                # See if the lock is stale. If so, remove it.
                try:
                    now = time.time()
                    mtime = os.path.getmtime(fn)
                    if (mtime + 60) < now:
                        os.unlink(fn)
                except OSError, e:
                    if e.errno != errno.ENOENT:
                        raise

                time.sleep(0.1)

            return True
        finally:
            self._lock.acquire()

    def _unlockSession(self, identifier):
        fn = self._filenameForSession(identifier) + '.lock'
        os.unlink(fn) # Need to catch errors?

    def _createSession(self, identifier):
        fn = self._filenameForSession(identifier)
        lfn = fn + '.lock'
        # Attempt to create the file's *lock* first.
        lfd = fd = -1
        try:
            lfd = os.open(lfn, os.O_WRONLY|os.O_CREAT|os.O_EXCL)
            fd = os.open(fn, os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        except OSError, e:
            if e.errno == errno.EEXIST:
                if lfd >= 0:
                    # Remove lockfile.
                    os.close(lfd)
                    os.unlink(lfn)
                return None
            raise
        else:
            # Success.
            os.close(fd)
            os.close(lfd)
            return self._sessionClass(identifier)

    def _loadSession(self, identifier, block=True):
        if not self._lockSession(identifier, block):
            return None
        try:
            return pickle.load(open(self._filenameForSession(identifier)))
        except:
            self._unlockSession(identifier)
            return None

    def _saveSession(self, session):
        f = open(self._filenameForSession(session.identifier), 'w+')
        pickle.dump(session, f, protocol=pickle.HIGHEST_PROTOCOL)
        f.close()
        self._unlockSession(session.identifier)

    def _deleteSession(self, identifier):
        try:
            os.unlink(self._filenameForSession(identifier))
        except:
            pass
        self._unlockSession(identifier)

    def _periodic(self):
        now = time.time()
        sessions = os.listdir(self._sessionDir)
        for name in sessions:
            if not name.endswith('.sess'):
                continue
            identifier = name[:-5]
            if not self._sessionClass.isIdentifierValid(identifier):
                continue
            # Not very efficient.
            sess = self._loadSession(identifier, block=False)
            if sess is None:
                continue
            if self._isSessionTimedout(sess, now):
                self._deleteSession(identifier)
            else:
                self._unlockSession(identifier)

    def _shutdown(self):
        pass

# SessionMiddleware stuff.

from Cookie import SimpleCookie
import cgi
import urlparse

class SessionService(object):
    """
    WSGI extension API passed to applications as
    environ['com.saddi.service.session'].

    Public API: (assume service = environ['com.saddi.service.session'])
      service.session - Returns the Session associated with the client.
      service.hasSession - True if the client is currently associated with
        a Session.
      service.isSessionNew - True if the Session was created in this
        transaction.
      service.hasSessionExpired - True if the client is associated with a
        non-existent Session.
      service.encodesSessionInURL - True if the Session ID should be encoded in
        the URL. (read/write)
      service.encodeURL(url) - Returns url encoded with Session ID (if
        necessary).
      service.cookieAttributes - Dictionary of additional RFC2109 attributes
        to be added to the generated cookie.
      service.forceCookieOutput - Normally False. Set to True to force
        output of the Set-Cookie header during this request.
    """
    _expiredSessionIdentifier = 'expired session'

    def __init__(self, store, environ,
                 cookieName='_SID_',
                 cookieExpiration=None, # Deprecated
                 cookieAttributes={},
                 fieldName='_SID_'):
        self._store = store
        self._cookieName = cookieName
        self._cookieExpiration = cookieExpiration
        self.cookieAttributes = dict(cookieAttributes)
        self.forceCookieOutput = False
        self._fieldName = fieldName

        self._session = None
        self._newSession = False
        self._expired = False
        self.encodesSessionInURL = False

        if __debug__: self._closed = False

        self._loadExistingSession(environ)

    def _loadSessionFromCookie(self, environ):
        """
        Attempt to load the associated session using the identifier from
        the cookie.
        """
        C = SimpleCookie(environ.get('HTTP_COOKIE'))
        morsel = C.get(self._cookieName, None)
        if morsel is not None:
            self._session = self._store.checkOutSession(morsel.value)
            self._expired = self._session is None

    def _loadSessionFromQueryString(self, environ):
        """
        Attempt to load the associated session using the identifier from
        the query string.
        """
        qs = cgi.parse_qsl(environ.get('QUERY_STRING', ''))
        for name,value in qs:
            if name == self._fieldName:
                self._session = self._store.checkOutSession(value)
                self._expired = self._session is None
                self.encodesSessionInURL = True
                break
        
    def _loadExistingSession(self, environ):
        """Attempt to associate with an existing Session."""
        # Try cookie first.
        self._loadSessionFromCookie(environ)

        # Next, try query string.
        if self._session is None:
            self._loadSessionFromQueryString(environ)

    def _sessionIdentifier(self):
        """Returns the identifier of the current session."""
        assert self._session is not None
        return self._session.identifier

    def _shouldAddCookie(self):
        """
        Returns True if the session cookie should be added to the header
        (if not encoding the session ID in the URL). The cookie is added if
        one of these three conditions are true: a) the session was just
        created, b) the session is no longer valid, or c) the client is
        associated with a non-existent session.
        """
        return self._newSession or \
               (self._session is not None and not self._session.isValid) or \
               (self._session is None and self._expired)
        
    def addCookie(self, headers):
        """Adds Set-Cookie header if needed."""
        if not self.encodesSessionInURL and \
               (self._shouldAddCookie() or self.forceCookieOutput):
            if self._session is not None:
                sessId = self._sessionIdentifier()
                expireCookie = not self._session.isValid
            else:
                sessId = self._expiredSessionIdentifier
                expireCookie = True

            C = SimpleCookie()
            name = self._cookieName
            C[name] = sessId
            C[name]['path'] = '/'
            if self._cookieExpiration is not None:
                C[name]['expires'] = self._cookieExpiration
            C[name].update(self.cookieAttributes)
            if expireCookie:
                # Expire cookie
                C[name]['expires'] = -365*24*60*60
                C[name]['max-age'] = 0
            headers.append(('Set-Cookie', C[name].OutputString()))

    def close(self):
        """Checks session back into session store."""
        if self._session is None:
            return
        # Check the session back in and get rid of our reference.
        self._store.checkInSession(self._session)
        self._session = None
        if __debug__: self._closed = True

    # Public API

    def _get_session(self):
        if __debug__: assert not self._closed
        if self._session is None:
            self._session = self._store.createSession()
            self._newSession = True

        assert self._session is not None
        return self._session
    session = property(_get_session, None, None,
                       'Returns the Session object associated with this '
                       'client')

    def _get_hasSession(self):
        if __debug__: assert not self._closed
        return self._session is not None
    hasSession = property(_get_hasSession, None, None,
                          'True if a Session currently exists for this client')

    def _get_isSessionNew(self):
        if __debug__: assert not self._closed
        return self._newSession
    isSessionNew = property(_get_isSessionNew, None, None,
                            'True if the Session was created in this '
                            'transaction')

    def _get_hasSessionExpired(self):
        if __debug__: assert not self._closed
        return self._expired
    hasSessionExpired = property(_get_hasSessionExpired, None, None,
                                 'True if the client was associated with a '
                                 'non-existent Session')

    # Utilities

    def encodeURL(self, url):
        """Encodes session ID in URL, if necessary."""
        if __debug__: assert not self._closed
        if not self.encodesSessionInURL or self._session is None:
            return url
        u = list(urlparse.urlsplit(url))
        q = '%s=%s' % (self._fieldName, self._sessionIdentifier())
        if u[3]:
            u[3] = q + '&' + u[3]
        else:
            u[3] = q
        return urlparse.urlunsplit(u)

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

class SessionMiddleware(object):
    """
    WSGI middleware that adds a session service. A SessionService instance
    is passed to the application in environ['com.saddi.service.session'].
    A references to this instance should not be saved. (A new instance is
    instantiated with every call to the application.)
    """
    _serviceClass = SessionService

    def __init__(self, store, application, serviceClass=None, **kw):
        self._store = store
        self._application = application
        if serviceClass is not None:
            self._serviceClass = serviceClass
        self._serviceKW = kw

    def __call__(self, environ, start_response):
        service = self._serviceClass(self._store, environ, **self._serviceKW)
        environ['com.saddi.service.session'] = service

        def my_start_response(status, headers, exc_info=None):
            service.addCookie(headers)
            return start_response(status, headers, exc_info)

        try:
            result = self._application(environ, my_start_response)
        except:
            # If anything goes wrong, ensure the session is checked back in.
            service.close()
            raise

        # The iterator must be unconditionally wrapped, just in case it
        # is a generator. (In which case, we may not know that a Session
        # has been checked out until completion of the first iteration.)
        return _addClose(result, service.close)

if __name__ == '__main__':
    mss = MemorySessionStore(timeout=5)
#    sss = ShelveSessionStore(timeout=5)
    dss = DiskSessionStore(timeout=5)
