#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 29-Nov-2012
# Last mod  : 08-May-2013
# -----------------------------------------------------------------------------

import time, random

class Upload:

	IS_NEW          = -1
	IS_INITIATED    = 0
	IS_STARTED      = 1
	IS_IN_PROGRESS  = 2
	IS_COMPLETED    = 3
	IS_FAILED       = 4

	def __init__( self, id=None ):
		self.reset()
		if id is not None: self.id = id
	
	def reset( self ):
		self.id       = int(time.time() * 100000) + random.randint(0,100)
		self.status   = self.IS_NEW
		self.created  = time.time()
		self.updated  = time.time()
		self.progress = 0.0
		self.data     = None
		self.meta     = dict()
		self.read     = 0
	
	def export( self ):
		return self.__dict__
	
class Uploader:
	"""A class that can easily be composed to support progressive upload of
	data"""

	CHUNK_SIZE        = 64 * 1024
	CLEANUP_THRESHOLD = 60 * 8

	def __init__( self, uploads=None ):
		# TODO: SHOULD MAX THE UPLOAD QUEUE...
		self.uploads = {} if upload is None else uploads
		self.chunkSize = cls.CHUNK_SIZE

	def upload( self, request, field="data" ):
		"""Starts a new upload, the data is extract from the given field."""
		# We start by cleaning up inactive 
		self.cleanup()
		upload      = self._createUploadInfo(request)
		data_file   = self._readRequest(request, upload, field, self.chunkSize)
		return upload_info, data_file

	def progress( self, request ):
		upload_id  = request.param("id")
		if self.uploads.has(upload_id):
			return request.returns(self.uploads.get(upload_id))
		else:
			# NOTE: Chrome will call progress before the POST has started
			return request.returns(dict(progress=0,status="starting"))

	def cleanup( self ):
		now = time.time()
		for key, value in self.uploads.items():
			if value.status == value.IS_COMPLETED or value.status == value.IS_FAILED:
				del self.uploads[key]
			# NOTE: Not sure about that
			# elif now - value.updated > self.UPLOAD_UPDATE_THRESHOLD:
			#	del self.uploads[key]

	def getUploadInfo( self, uid ):
		return self.uploads.get(uid)

	def _createUploadInfo( self, request ):
		upload = Upload(id=request.param("id"))
		self.uploads.set(upload_id, upload)
		return upload

	def _readRequest( self, request, upload, field, chunkSize ):
		while not request.isLoaded():
			data              = request.load(chunkSize)
			progress          = request.loadProgress()
			info["progress"]  = min(99,progress)
			info["status"]    = "uploading"
			info["bytesRead"] = request.loadProgress(inBytes=True)
			info["updated"]   = time.time()
		info["status"]  = "uploaded"
		info["updated"] = time.time()
		return request.file(field)

# EOF
