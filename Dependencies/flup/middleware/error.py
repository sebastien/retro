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
# $Id: error.py 1753 2005-04-15 01:33:10Z asaddi $

__author__ = 'Allan Saddi <allan@saddi.com>'
__version__ = '$Revision: 1753 $'

import sys
import os
import traceback
import time
from email.Message import Message
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import smtplib

try:
    import thread
except ImportError:
    import dummy_thread as thread

__all__ = ['ErrorMiddleware']

def _wrapIterator(appIter, errorMiddleware, environ, start_response):
    """
    Wrapper around the application's iterator which catches any unhandled
    exceptions. Forwards close() and __len__ to the application iterator,
    if necessary.
    """
    class metaIterWrapper(type):
        def __init__(cls, name, bases, clsdict):
            super(metaIterWrapper, cls).__init__(name, bases, clsdict)
            if hasattr(appIter, '__len__'):
                cls.__len__ = appIter.__len__

    class iterWrapper(object):
        __metaclass__ = metaIterWrapper
        def __init__(self):
            self._next = iter(appIter).next
            if hasattr(appIter, 'close'):
                self.close = appIter.close

        def __iter__(self):
            return self

        def next(self):
            try:
                return self._next()
            except StopIteration:
                raise
            except:
                errorMiddleware.exceptionHandler(environ)

                # I'm not sure I like this next part.
                try:
                    errorIter = errorMiddleware.displayErrorPage(environ,
                                                                 start_response)
                except:
                    # Headers already sent, what can be done?
                    raise
                else:
                    # The exception occurred early enough for start_response()
                    # to succeed. Swap iterators!
                    self._next = iter(errorIter).next
                    return self._next()

    return iterWrapper()

class ErrorMiddleware(object):
    """
    Middleware that catches any unhandled exceptions from the application.
    Displays a (static) error page to the user while emailing details about
    the exception to an administrator.
    """
    def __init__(self, application, adminAddress,
                 fromAddress='wsgiapp',
                 smtpHost='localhost',

                 applicationName=None,

                 errorPageMimeType='text/html',
                 errorPage=None,
                 errorPageFile='error.html',

                 emailInterval=15,
                 intervalCheckFile='errorEmailCheck',

                 debug=False):
        """
        Explanation of parameters:

        application - WSGI application.

        adminAddress - Email address of administrator.
        fromAddress - Email address that the error email should appear to
          originate from. By default 'wsgiapp@hostname.of.server'.
        smtpHost - SMTP email server, through which to send the email.

        applicationName - Name of your WSGI application, to help differentiate
          it from other applications in email. By default, this is the Python
          name of the application object. (You should explicitly set this
          if you use other middleware components, otherwise the name
          deduced will probably be that of a middleware component.)

        errorPageMimeType - MIME type of the static error page. 'text/html'
          by default.
        errorPage - String representing the body of the static error page.
          If None (the default), errorPageFile must point to an existing file.
        errorPageFile - File from which to take the static error page (may
          be relative to current directory or an absolute filename).

        emailInterval - Minimum number of minutes between error mailings,
          to prevent the administrator's mailbox from filling up.
        intervalCheckFile - When running in one-shot mode (as determined by
          the 'wsgi.run_once' environment variable), this file is used to
          keep track of the last time an email was sent. May be relative
          (to the current directory) or an absolute filename.

        debug - If True, will attempt to display the traceback as a webpage.
          No email is sent. If False (the default), the static error page is
          displayed and the error email is sent, if necessary.
        """
        self._application = application

        self._adminAddress = adminAddress
        self._fromAddress = fromAddress
        self._smtpHost = smtpHost

        # Set up a generic application name if not specified.
        if applicationName is None:
            applicationName = []
            if application.__module__ != '__main__':
                applicationName.append('%s.' % application.__module__)
            applicationName.append(application.__name__)
            applicationName = ''.join(applicationName)
        self._applicationName = applicationName

        self._errorPageMimeType = errorPageMimeType
        # If errorPage was unspecified, set it from the static file
        # specified by errorPageFile.
        if errorPage is None:
            f = open(errorPageFile)
            errorPage = f.read()
            f.close
        self._errorPage = errorPage

        self._emailInterval = emailInterval * 60
        self._lastEmailTime = 0
        self._intervalCheckFile = intervalCheckFile

        # Set up displayErrorPage appropriately.
        self._debug = debug
        if debug:
            self.displayErrorPage = self._displayDebugPage
        else:
            self.displayErrorPage = self._displayErrorPage

        # Lock for _lastEmailTime
        self._lock = thread.allocate_lock()

    def _displayErrorPage(self, environ, start_response):
        """
        Displays the static error page. May be overridden. (Maybe you'd
        rather redirect or something?) This is basically a mini-WSGI
        application, except that start_response() is called with the third
        argument.

        Really, there's nothing keeping you from overriding this method
        and displaying a dynamic error page. But I thought it might be safer
        to display a static page. :)
        """
        start_response('200 OK', [('Content-Type', self._errorPageMimeType),
                                  ('Content-Length',
                                   str(len(self._errorPage)))],
                       sys.exc_info())
        return [self._errorPage]

    def _displayDebugPage(self, environ, start_response):
        """
        When debugging, display an informative traceback of the exception.
        """
        import cgitb
        result = [cgitb.html(sys.exc_info())]
        start_response('200 OK', [('Content-Type', 'text/html'),
                                  ('Content-Length', str(len(result[0])))],
                       sys.exc_info())
        return result

    def _generateHTMLErrorEmail(self):
        """
        Generates the HTML version of the error email. Must return a string.
        """
        import cgitb
        return cgitb.html(sys.exc_info())

    def _generatePlainErrorEmail(self):
        """
        Generates the plain-text version of the error email. Must return a
        string.
        """
        import cgitb
        return cgitb.text(sys.exc_info())

    def _generateErrorEmail(self):
        """
        Generates the error email. Must return an instance of email.Message
        or subclass.

        This implementation generates a MIME multipart/alternative email with
        an HTML description of the error and a simpler plain-text alternative
        of the traceback.
        """
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(self._generatePlainErrorEmail()))
        msg.attach(MIMEText(self._generateHTMLErrorEmail(), 'html'))
        return msg

    def _sendErrorEmail(self, environ):
        """
        Sends the error email as generated by _generateErrorEmail(). If
        anything goes wrong sending the email, the exception is caught
        and reported to wsgi.errors. I don't think there's really much else
        that can be done in that case.
        """
        msg = self._generateErrorEmail()

        msg['From'] = self._fromAddress
        msg['To'] = self._adminAddress
        msg['Subject'] = '%s: unhandled exception' % self._applicationName

        try:
            server = smtplib.SMTP(self._smtpHost)
            server.sendmail(self._fromAddress, self._adminAddress,
                            msg.as_string())
            server.quit()
        except Exception, e:
            stderr = environ['wsgi.errors']
            stderr.write('%s: Failed to send error email: %r %s\n' %
                         (self.__class__.__name__, e, e))
            stderr.flush()

    def _shouldSendEmail(self, environ):
        """
        Returns True if an email should be sent. The last time an email was
        sent is tracked by either an instance variable (if oneShot is False),
        or the mtime of a file on the filesystem (if oneShot is True).
        """
        if self._debug or self._adminAddress is None:
            # Never send email when debugging or when there's no admin
            # address.
            return False

        now = time.time()
        if not environ['wsgi.run_once']:
            self._lock.acquire()
            ret = (self._lastEmailTime + self._emailInterval) < now
            if ret:
                self._lastEmailTime = now
            self._lock.release()
        else:
            # The following should be protected, but do I *really* want
            # to get into the mess of using filesystem and file-based locks?
            # At worse, multiple emails get sent.
            ret = True

            try:
                mtime = os.path.getmtime(self._intervalCheckFile)
            except:
                # Assume file doesn't exist, which is OK. Send email
                # unconditionally.
                pass
            else:
                if (mtime + self._emailInterval) >= now:
                    ret = False

            if ret:
                # NB: If _intervalCheckFile cannot be created or written to
                # for whatever reason, you will *always* get an error email.
                try:
                    open(self._intervalCheckFile, 'w').close()
                except:
                    # Probably a good idea to report failure.
                    stderr = environ['wsgi.errors']
                    stderr.write('%s: Error writing intervalCheckFile %r\n'
                                 % (self.__class__.__name__,
                                    self._intervalCheckFile))
                    stderr.flush()
        return ret

    def exceptionHandler(self, environ):
        """
        Common handling of exceptions.
        """
        # Unconditionally report to wsgi.errors.
        stderr = environ['wsgi.errors']
        traceback.print_exc(file=stderr)
        stderr.flush()

        # Send error email, if needed.
        if self._shouldSendEmail(environ):
            self._sendErrorEmail(environ)

    def __call__(self, environ, start_response):
        """
        WSGI application interface. Simply wraps the call to the application
        with a try ... except. All the fancy stuff happens in the except
        clause.
        """
        try:
            return _wrapIterator(self._application(environ, start_response),
                                 self, environ, start_response)
        except:
            # Report the exception.
            self.exceptionHandler(environ)

            # Display static error page.
            return self.displayErrorPage(environ, start_response)

if __name__ == '__main__':
    def myapp(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        raise RuntimeError, "I'm broken!"
        return ['Hello World!\n']

    # Note - email address is taken from sys.argv[1]. I'm not leaving
    # my email address here. ;)
    app = ErrorMiddleware(myapp, sys.argv[1])

    from ajp import WSGIServer
    WSGIServer(app).run()
