#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 29-Nov-2012
# Last mod  : 10-May-2013
# -----------------------------------------------------------------------------

import time, random

# -----------------------------------------------------------------------------
#
# UPLOAD
#
# -----------------------------------------------------------------------------

class Upload:
	"""Wraps a request and provides convenient methods/callbacks to monitor
	the uploading/decoding of the request."""

	IS_NEW          = 0
	IS_STARTED      = 1
	IS_IN_PROGRESS  = 2
	IS_DECODING     = 4
	IS_COMPLETED    = 5
	IS_FAILED       = 6
	CHUNK_SIZE      = 64 * 1024

	def __init__( self, uid=None, request=None):
		self.callbacks = {}
		self.reset()
		if uid is not None: self.uid = str(uid)
		if request: self.setRequest(request)

	def onStatus( self, value, callback ):
		self.callbacks.setdefault(value,[]).append(callback)

	def onCompleted( self, callback ): return self.onStatus(self.IS_COMPLETED,   callback)
	def onFailed( self, callback ):    return self.onStatus(self.IS_FAILED,      callback)
	def onProgress( self, callback ):  return self.onStatus(self.IS_IN_PROGRESS, callback)

	def setStatus( self, status ):
		# We change the status already
		self.status = status
		if status in self.callbacks:
			for _ in self.callbacks[status]:
				#try:
				_(self)
				# except Exception, e:
				# 	self.fail(e)
				# 	raise e
		return status

	def reset( self ):
		self.uid       = str(int(time.time() * 100000) + random.randint(0,100))
		self.request   = None
		self.created   = time.time()
		self.updated   = time.time()
		self.progress  = 0.0
		self.data      = None
		self.meta      = {}
		self.bytesRead     = 0
		self.lastBytesRead = 0
		self.setStatus(self.IS_NEW)

	def setRequest( self, request ):
		self.request = request
		self.setStatus(self.IS_STARTED)
		return self

	def getFiles( self, chunksize=None ):
		"""Reads the request and generated `(self.progress, [request.core.File])`
		couples until the load is complete."""
		for _ in self.read(chunksize):
			yield (self.progress, None)
			if self.status == self.IS_COMPLETED:
				yield (100, self.request.files())

	def getFile( self, name, chunksize=None ):
		"""Reads the request and generated `(self.progress, request.core.File)`
		couples until the load is complete."""
		for _ in self.read(chunksize):
			yield (self.progress, None)
			if self.status == self.IS_COMPLETED:
				yield (100, self.request.file(name))

	def read( self, chunksize=None ):
		"""Returns a generator that yields the upload object each time
		a chunk is read."""
		chunksize = self.CHUNK_SIZE if chunksize is None else chunksize
		data      = None
		while not self.request.isLoaded():
			data               = self.request.load(chunksize, decode=False)
			last_bytes         = self.bytesRead
			self.bytesRead     = self.request.loadProgress(inBytes=True)
			self.lastBytesRead = self.bytesRead - last_bytes
			self.progress      = self.request.loadProgress()
			self.updated       = time.time()
			self.setStatus(self.IS_IN_PROGRESS)
			# We consume the data so as not to keep the file in memory
			yield self
		last_bytes         = self.bytesRead
		self.bytesRead     = self.request.loadProgress(inBytes=True)
		self.lastBytesRead = self.bytesRead - last_bytes
		self.progress      = self.request.loadProgress()
		self.setStatus(self.IS_DECODING)
		yield self
		self.request.load(decode=True)
		self.setStatus(self.IS_COMPLETED)
		self.updated       = time.time()
		yield self

	def fail( self, error=None ):
		self.setStatus(self.IS_FAILED)
		self.meta["error"] = str(error)

	def __iter__( self ):
		for _ in self.read(self.CHUNK_SIZE):
			yield _

	def export( self ):
		return dict(
			uid=self.uid,
			data=self.data,
			meta=self.meta,
			status=self.status,
			created=self.created,
			updated=self.updated,
			progress=self.progress,
			bytesRead=self.bytesRead,
			lastBytesRead=self.lastBytesRead,
		)

# -----------------------------------------------------------------------------
#
# UPLOADER
#
# -----------------------------------------------------------------------------

class Uploader:
	"""A class that can easily be composed to support progressive upload of
	data with accessible information on the progress."""

	CLEANUP_THRESHOLD = 60 * 8

	def __init__( self, uploads=None ):
		# TODO: SHOULD MAX THE UPLOAD QUEUE...
		self.uploads = {} if uploads is None else uploads

	def upload( self, request, uploadID=None, chunksize=None ):
		"""Starts a new upload, the data is extract from the given field
		(`data` by default). This returns the corresponding `Upload` instance
		and a file object to the data file.
		"""
		# We start by cleaning up inactive
		self.cleanup()
		upload        = Upload(request=request, uid=request.param("uid") if uploadID is None else uploadID)
		if chunksize: upload.CHUNK_SIZE = chunksize
		self.uploads[upload.uid] = upload
		return upload

	def get( self, uploadID ):
		"""Returns the upload with the given ID."""
		if uploadID in self.uploads:
			return self.uploads[uploadID]
		else:
			# NOTE: In some cases you might want to poll the progress
			# before the startUpload has actually been started, in this
			# case, we return a temporary dummy new upload.
			upload      = Upload(uid=uploadID)
			self.uploads[upload.uid] = upload
			return upload

	def cleanup( self ):
		now = time.time()
		to_remove = []
		for key, value in list(self.uploads.items()):
			if value.status == value.IS_COMPLETED or value.status == value.IS_FAILED:
				to_remove.append(key)
			# NOTE: Not sure about that
			elif now - value.updated > self.CLEANUP_THRESHOLD:
				to_remove.append(key)
		for key in to_remove:
			if key in self.uploads:
				del self.uploads[key]
		return len(to_remove)

# EOF - vim: ts=4 sw=4 noet
