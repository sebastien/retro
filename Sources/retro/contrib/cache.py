#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 07-Nov-2007
# Last mod  : 18-Jul-2012
# -----------------------------------------------------------------------------

import os, stat, hashlib, threading, urllib, pickle, time

class CacheError(Exception):
	pass

class CacheMiss(Exception):
	pass

# -----------------------------------------------------------------------------
#
# CACHE OBJECT
#
# -----------------------------------------------------------------------------

class Cache:

	def __init__( self ):
		self.enabled = True

	def get( self, key ):
		raise NotImplementedError
	
	def has( self, key ):
		raise NotImplementedError

	def set( self, key, value ):
		raise NotImplementedError
	
	def clear( self, key ):
		raise NotImplementedError

	def remove( self, key ):
		raise NotImplementedError

	def keys( self ):
		raise NotImplementedError

	def cleanup( self ):
		raise NotImplementedError

	def wrap(self, keyExtractor):
		def wrap_wrapper(function):
			def operation(*args, **kwargs):
				key = keyExtractor(*args, **kwargs)
				if self.has(key):
					return self.get(key)
				else:
					res = function(*args,**kwargs)
					self.set(key, res)
					return res
			return operation
		return wrap_wrapper

	def __setitem__( self, key, value ):
		return self.set(key, value)

	def __getitem__( self, key ):
		return self.get(key)

	def __iter__( self ):
		for k in self.keys():
			yield k

# -----------------------------------------------------------------------------
#
# NO CACHE
#
# -----------------------------------------------------------------------------

class NoCache(Cache):

	def __init__( self ):
		Cache.__init__(self)

	def get( self, key ):
		return False
	
	def has( self, key ):
		return False

	def set( self, key, value ):
		return False
	
	def clear( self, key ):
		return False

	def remove( self, key ):
		return False

	def cleanup( self ):
		pass

	def keys( self ):
		return ()

# -----------------------------------------------------------------------------
#
# MEMORY CACHE
#
# -----------------------------------------------------------------------------

class MemoryCache(Cache):
	"""A simple cache that wraps a dictionary with a limit."""

	def __init__( self, limit=100 ):
		Cache.__init__(self)
		# Data is key => [WEIGHT, HITS, TIMESTAMP VALUE]
		self.data    = {}
		self.limit   = limit
		self.enabled = True

	def enable( self ):
		self.enabled = True

	def disable( self ):
		self.enabled = False

	def get( self, key ):
		return self.data.get(key)

	def has( self, key ):
		res = self.data.get(key)
		return res and True

	def set( self, key, data ):
		self.cleanup()
		self.data[key] = data
		return data

	def clear( self ):
		self.data = {}
	
	def keys( self ):
		return self.data.keys()

	def remove( self, key ):
		self.lock.acquire()
		if self.data.has_key(key):
			# NOTEL This is the  same as in cleanuip
			self.weight -= self.data[key][self.WEIGHT]
			del self.data[key]
		self.lock.release()

	def cleanup( self ):
		if len(self.data) >= self.limit:
			keys = []
			for k in self.data:
				keys.append(k)
				if len(self.data) - len(keys) < self.limit:
					break
			for k in keys:
				del self.data[k]

# -----------------------------------------------------------------------------
#
# LRU CACHE
#
# -----------------------------------------------------------------------------

class LRUCache(Cache):
	"""A simple in-memory cache using a weighted LRU style dictionary,
	 with an optional timeout for kept values (in seconds)."""

	WEIGHT     = 0
	HITS       = 1
	TIMESTAMP  = 2
	VALUE      = 3

	def __init__( self, limit=100, timeout=-1 ):
		Cache.__init__(self)
		# Data is key => [WEIGHT, HITS, TIMESTAMP VALUE]
		self.data    = {}
		self.weight  = 0
		self.limit   = limit
		self.timeout = timeout
		self.lock    = threading.RLock()
		self.enabled = True

	def enable( self ):
		self.enabled = True

	def disable( self ):
		self.enabled = False

	def get( self, key ):
		d = self.data.get(key)
		if d:
			if self.timeout <= 0 or (time.time() - d[self.TIMESTAMP]) < self.timeout:
				# We increase the hit count
				d[self.HITS] += 1
				return d[self.VALUE]
			else:
				self.remove(key)
				return None
		else:
			return None

	def has( self, key ):
		res = self.data.get(key)
		return res and True

	def set( self, key, data, weight=1 ):
		self.lock.acquire()
		if self.data.has_key(key):
			# We update the data if it's already there
			previous       = self.data[key]
			self.weight   -= previous[self.WEIGHT]
			previous[self.WEIGHT]    = weight
			previous[self.TIMESTAMP] = time.time()
			previous[self.VALUE]     = data
			self.data[key] = previous
		else:
			self.data[key] = [weight, 0, time.time(), data]
			self.weight   += weight
		self.lock.release()
		if self.weight > self.limit:
			self.cleanup()
		return data

	def clear( self ):
		self.data = {}

	def keys( self ):
		return self.data.keys()

	def remove( self, key ):
		self.lock.acquire()
		if self.data.has_key(key):
			# NOTEL This is the  same as in cleanuip
			self.weight -= self.data[key][self.WEIGHT]
			del self.data[key]
		self.lock.release()

	def cleanup( self ):
		self.lock.acquire()
		now   = time.time()
		# We remove older items
		if self.timeout > 0:
			for key in self.data.keys():
				if now - self.data[key][self.TIMESTAMP] > self.timeout:
					del self.data[key]
		items = self.data.items()
		# FIXME: This is slooooow
		# We compare the hits
		items.sort(lambda a,b:cmp(a[1][self.HITS], b[1][self.HITS]))
		i = 0
		while self.weight > self.limit and i < len(items):
			key, value = items[i]
			# NOTE: This is the same as remove
			self.weight -= value[self.WEIGHT]
			del self.data[key]
			i += 1
		self.lock.release()

# -----------------------------------------------------------------------------
#
# TIMEOUT CACHE
#
# -----------------------------------------------------------------------------

# FIXME: Timeout is not useful unless it has cleanup -- we should refactor this
class TimeoutCache(Cache):

	def __init__( self, cache=None, timeout=10, limit=100 ):
		Cache.__init__(self)
		self.cache   = cache or MemoryCache(limit=limit)
		self.timeout = timeout
	
	def get( self, key ):
		if self.cache.has(key):
			value, insert_time = self.cache.get(key)
			if (time.time() - insert_time)  < self.timeout:
				return value
			else:
				return None
		else:
			return None

	def hasTimedOut( self, key ):
		value, insert_time = self.cache.get(key)
		return (time.time() - insert_time) > self.timeout

	def has( self, key ):
		if self.cache.has(key):
			return not self.hasTimedOut(key)
		else:
			return False

	def set( self, key, value ):
		self.cache.set(key, (value, time.time()))
		return value
	
	def clear( self ):
		self.cache.clear()

	def keys( self ):
		return self.cache.keys()

	def remove( self, key ):
		self.cache.remove(key)

	def cleanup( self ):
		for key in self.cache.keys():
			if self.hasTimedOut(key):
				self.cache.remove(key)
		return self

# -----------------------------------------------------------------------------
#
# FILE CACHE
#
# -----------------------------------------------------------------------------

class FileCache(Cache):
	"""A simplistic filesystem-based cache"""

	EXTENSION = ".cache"
	EXPIRES   = 60 * 60

	# FIXME: Should split paths when they exceed the file name limit (256 bytes)
	@staticmethod
	def SHA1_KEY(_):return hashlib.sha1(_).hexdigest()
	@staticmethod
	def MD5_KEY (_):return hashlib.md5(_).hexdigest()
	@classmethod
	def NAME_KEY(self,key):
		max_length = 100 - len(self.EXTENSION)
		key = urllib.urlencode(dict(_=key))[2:]
		if len(key) >= max_length:
			suffix = hashlib.md5(key).hexdigest()
			key    = key[:max_length - (len(suffix) + 2)] + "-" + suffix
		assert len(key) < max_length, "Key is too long %d > %d" % (len(key), max_length)
		return key

	def __init__( self, path=None, serializer=lambda fd,data:pickle.dump(data,fd), deserializer=pickle.load, keys=None):
		Cache.__init__(self)
		self.serializer   = serializer
		self.deserializer = deserializer
		self.setPath(path)
		self.keyProcessor = keys or self.NAME_KEY
		self.enabled      = True
	
	def noExpire( self ):
		"""Disables cache expiration."""
		self.EXPIRES = 0

	def withSHA1Keys( self ):
		self.setKeyProcessor(FileCache.SHA1_KEY)
		return self

	def withMD5Keys( self ):
		self.setKeyProcessor(FileCache.SHA1_KEY)
		return self
	
	def setKeyProcessor( self, keys ):
		self.keyProcessor = keys
		return self

	def setPath( self, path ):
		path = path or "."
		if len(path) > 1 and path[-1] == "/": path = path[:-1]
		assert os.path.exists(path)
		assert os.path.isdir(path)
		self.path = path

	def has( self, key ):
		path = self.path + "/" + self._normKey(key) + self.EXTENSION
		if os.path.exists(path):
			s = os.stat(path)
			if self.EXPIRES > 0:
				return (time.time() - s[stat.ST_MTIME]) < self.EXPIRES
			else:
				return True
		else:
			return False

	def get( self, key ):
		if self.has(key):
			path = self.path + "/" + self._normKey(key) + self.EXTENSION
			with file(path, 'r') as f:
				return self._load(f)
		else:
			return None

	def set( self, key, data ):
		path = self.path + "/" + self._normKey(key) + self.EXTENSION
		with file(path, 'w') as f:
			self._save(f, data)
		return data

	def clear( self ):
		assert False, "Not implemented"
		
	def remove( self, key):
		if self.has(key):
			os.unlink(self.path + "/" + self._normKey(key) + self.EXTENSION)

	def _normKey( self, key ):
		return self.keyProcessor(key)
	
	def _save( self, fd, data ):
		try:
			return self.serializer(fd, data)
		except Exception, e:
			return None

	def _load( self, fd ):
		try:
			return self.deserializer(fd)
		except Exception, e:
			return None

# -----------------------------------------------------------------------------
#
# SIGNATURE CACHE
#
# -----------------------------------------------------------------------------

class SignatureCache(Cache):
	"""A specific type of cache that takes a signature."""

	def __init__( self, backend=None ):
		Cache.__init__(self)
		# TODO: Add cache clearing functions
		self._cachedSig  = {}
		self._backend    = backend or MemoryCache()
		self.enabled     = True


	def clear( self ):
		self._cachedSig = {}
		self.backend.clear()

	def has( self, key, sig=0 ):
		"""Tells if this cache has the value for the given key and signature."""
		return self._cachedSig.has_key(key) and (self._cachedSig.get(key) == sig)
	
	def get( self, key, sig=0 ):
		"""Returns a couple (updaToDate, data) for the given key and
		signature. If the signature is different, then (False, None) is returned
		and the previous data is cleared from the cache."""
		if self._cachedSig.get(key) != sig:
			self._backend.remove(key)
			return False, None
		else:
			return True, self._backend.get(key)

	def set( self, key, sig, data ):
		"""Associates the given data with the give key and signature."""
		self._cachedSig[key]  = sig
		self._backend.set(key, data)
		return data

	@staticmethod
	def sha1(  path ):
		f = file(path, 'rb')
		t = f.read()
		f.close()
		return hashlib.sha1(t).hexdigest()

	@staticmethod
	def mtime( path):
		try:
			return  os.stat(path)[stat.ST_MTIME]
		except Exception, e:
			return None


# EOF - vim: tw=80 ts=4 sw=4 noet
