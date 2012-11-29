import time

class Uploader:
	"""A class that can easily be composed to support progressive upload of
	data"""

	def __init__( self ):
		self.uploads = {}

	def upload( self, request, chunkSize=1024*64, field="data" ):
		# We start by cleaning up inactive 
		self.cleanup()
		upload_info = self._createUploadInfo(request)
		data_file   = self._readRequest(request, upload_info, field, chunkSize)
		return upload_info, data_file

	def progress( self, request ):
		upload_id  = request.param("id")
		if self.uploads.has(upload_id):
			return request.returns(self.uploads.get(upload_id))
		else:
			# NOTE: Chrome will call progress before the POST has started
			return request.returns(dict(progress=0,status="starting"))

	def cleanup( self ):
		pass

	def getUploadInfo( self, uid ):
		return self.uploads.get(uid)

	def _createUploadInfo( self, request ):
		upload_id = request.param("id")
		info      = {"id":upload_id, "progress":0,"status":"started","bytesRead":0,"created":time.time(), "updated":time.time()}
		self.uploads.set(upload_id, info)
		return info

	def _readRequest( self, request, info, field, chunkSize ):
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
