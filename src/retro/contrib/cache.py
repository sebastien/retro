#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 07-Nov-2007
# Last mod  : 14-Feb-2019
# -----------------------------------------------------------------------------

import re, os, stat, hashlib, threading,  pickle, time, functools, types
from   retro.web import cache_id, cache_signature
try:
	from urllib.parse import urlencode
except ImportError:
	from urllib       import urlencode

RE_FILE_ESCAPE = re.compile("[\:\<\>/\(\)\[\]\{\}\$\~]|\.\.")

class CacheError(Exception):
	pass

class CacheMiss(Exception):
	pass

def cached( store, prefix=None ):
	"""A generic decorator that can be used to cache any function."""
	def decorator( f ):
		def wrapper( *args, **kwargs ):
			key      = f.__name__
			base_key = ",".join(map(cache_id, args))
			rest_key = ",".join([kv[0] + "=" + kv[1] for kv in list(map(cache_id, list(kwargs.items())))])
			key      += "(" + (",".join((base_key, rest_key))) + ")"
			if prefix: key = prefix + ":" + key
			if store.enabled:
				if store.has(key):
					return store.get(key)
				else:
					result = f(*args, **kwargs)
					store.set(key, result)
					return result
			else:
				return f(*args, **kwargs)
		functools.update_wrapper(wrapper, f)
		return wrapper
	return decorator

# -----------------------------------------------------------------------------
#
# CACHE OBJECT
#
# -----------------------------------------------------------------------------

class Cache:

	NEVER = 0

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

	def invalidate( self, key ):
		if type(key) in (str, unicode):
			if self.has(key):
				self.remove(key)
		elif isinstance(key, types.FunctionType) or isinstance(key, types.MethodType):
			prefix = key.__name__ + ":"
			to_remove = [k for k in self.keys() if k.startswith(prefix)]
			for k in to_remove: self.remove(k)
		else:
			raise Exception("Unsupported key type {0}: {1}".format(type(key), key))
		return self

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
		for k in list(self.keys()):
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
	"""A simple cache that wraps a dictionary with a limit. Oldest entries
	are automatically removed."""

	def __init__( self, limit=100 ):
		Cache.__init__(self)
		# Data is key => [WEIGHT, HITS, TIMESTAMP VALUE]
		self.data     = {}
		self.limit    = limit
		self.enabled  = True

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
		return list(self.data.keys())

	def remove( self, key ):
		if key in self.data:
			del self.data[key]

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
	EXPIRES    = -1

	def __init__( self, limit=100, expires=None ):
		Cache.__init__(self)
		# Data is key => [WEIGHT, HITS, TIMESTAMP VALUE]
		self.data    = {}
		self.weight  = 0
		self.limit   = limit
		self.lock    = threading.RLock()
		self.enabled = True
		if expires is not None: self.expires(expires)

	def expires( self, value ):
		self.EXPIRES = value
		return self

	def enable( self ):
		self.enabled = True

	def disable( self ):
		self.enabled = False

	def get( self, key ):
		d = self.data.get(key)
		if d:
			if self.EXPIRES <= 0 or (time.time() - d[self.TIMESTAMP]) < self.EXPIRES:
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
		if key in self.data:
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
		return list(self.data.keys())

	def remove( self, key ):
		self.lock.acquire()
		if key in self.data:
			# NOTEL This is the  same as in cleanuip
			self.weight -= self.data[key][self.WEIGHT]
			del self.data[key]
		self.lock.release()

	def cleanup( self ):
		self.lock.acquire()
		now   = time.time()
		# We remove older items
		if self.EXPIRES > 0:
			for key in list(self.data.keys()):
				if now - self.data[key][self.TIMESTAMP] > self.EXPIRES:
					del self.data[key]
		items = list(self.data.items())
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

	TIMEOUT = 60 * 60

	def __init__( self, cache=None, timeout=None, limit=-1 ):
		Cache.__init__(self)
		self.cache   = cache or MemoryCache(limit=limit)
		self.timeout = self.TIMEOUT if timeout is None else timeout

	def get( self, key ):
		if self.cache.has(key):
			value, insert_time = self.cache.get(key)
			# We don't call hasTimedOut directly as we want to save another
			# query to the cache
			if (time.time() - insert_time)  < self.timeout:
				return value
			else:
				# Key is out of date
				self.remove(key)
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
		return list(self.cache.keys())

	def remove( self, key ):
		self.cache.remove(key)

	def cleanup( self ):
		for key in list(self.cache.keys()):
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

	EXTENSION       = ".cache"
	EXPIRES         = 60 * 60
	MAX_KEY_LENGTH = 100

	@staticmethod
	def SHA1_KEY(_):
		return hashlib.sha1(bytes(_, "UTF8")).hexdigest()

	@staticmethod
	def MD5_KEY (_):
		return hashlib.md5(bytes(_, "UTF8")).hexdigest()

	@classmethod
	def NAME_KEY(self,key):
		max_length = self.MAX_KEY_LENGTH - len(self.EXTENSION)
		name       = urlencode(dict(_=key))[2:]
		name_len   = len(name)
		if name_len >= max_length:
			suffix = hashlib.md5(bytes(key, "UTF8")).hexdigest()
			name   = name[:max_length - (len(suffix) + 1)]
			name  += "-" + suffix
		if not (len(name) <= max_length):
			import ipdb
			ipdb.set_trace()
		assert len(name) <= max_length, "Key is too long %d > %d, key=%s" % (len(name), max_length, repr(key))
		return name

	def __init__( self, path=".cache", serializer=lambda fd,data:pickle.dump(data,fd), deserializer=pickle.load, keys=None, expires=None, createPath=True, extension=None):
		Cache.__init__(self)
		self.serializer   = serializer
		self.deserializer = deserializer
		self.setPath(path, createPath)
		self.keyProcessor = keys or self.NAME_KEY
		self.extension    = extension or self.EXTENSION
		self.enabled      = True
		if expires != None:self.EXPIRES = expires

	def expires( self, value ):
		self.EXPIRES = value
		return self

	def noExpire( self ):
		"""Disables cache expiration."""
		self.EXPIRES = 0
		return self

	def withSHA1Keys( self ):
		self.setKeyProcessor(FileCache.SHA1_KEY)
		return self

	def withMD5Keys( self ):
		self.setKeyProcessor(FileCache.SHA1_KEY)
		return self

	def setKeyProcessor( self, keys ):
		self.keyProcessor = keys
		return self

	def setPath( self, path , createPath=True):
		path = path or "."
		if len(path) > 1 and path[-1] == "/": path = path[:-1]
		if createPath and not os.path.exists(path): os.makedirs(path)
		assert os.path.exists(path), "Cache path does not exist: {0}".format(path)
		assert os.path.isdir(path),  "Cache path is not a directory: {0}".format(path)
		self.path = path

	def mtime( self, key ):
		path = self.path + "/" + self._normKey(key) + self.extension
		if os.path.exists(path):
			return os.stat(path)[stat.ST_MTIME]
		else:
			return None

	def has( self, key ):
		path = self.path + "/" + self._normKey(key) + self.extension
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
			path = self.path + "/" + self._normKey(key) + self.extension
			with open(path, 'rb') as f:
				res = self._load(f)
				return res
		else:
			return None

	def set( self, key, data ):
		path = self.path + "/" + self._normKey(key) + self.extension
		with open(path, 'wb') as f:
			success = self._save(f, data)
		if not success: os.unlink(path)
		return data

	def clear( self ):
		assert False, "Not implemented"

	def remove( self, key):
		if self.has(key):
			os.unlink(self.path + "/" + self._normKey(key) + self.extension)

	def _normKey( self, key ):
		return self.keyProcessor(key)

	def _save( self, fd, data ):
		try:
			self.serializer(fd, data)
			return True
		except Exception as e:
			return False

	def _load( self, fd ):
		try:
			return self.deserializer(fd)
		except Exception as e:
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
		return key in self._cachedSig and (self._cachedSig.get(key) == sig)

	def get( self, key, sig=0 ):
		"""Returns a couple (upToDate, data) for the given key and
		signature. If the signature is different, then (False, None) is returned
		and the previous data is cleared from the cache."""
		if self._cachedSig.get(key) != sig or not self._backend.has(key):
			self._backend.remove(key)
			return False, None
		else:
			return True, self._backend.get(key)

	def set( self, key, sig, data ):
		"""Associates the given data with the give key and signature."""
		self._cachedSig[key]  = sig
		self._backend.set(key, data)
		return data

	def keys( self ):
		return self._cachedSig.keys()

	@staticmethod
	def sha1(  path ):
		with open(path, 'rb') as f:
			t = f.read()
		return hashlib.sha1(t).hexdigest()

	@staticmethod
	def mtime( path):
		try:
			return  os.stat(path)[stat.ST_MTIME]
		except Exception as e:
			return None


# EOF - vim: tw=80 ts=4 sw=4 noet
