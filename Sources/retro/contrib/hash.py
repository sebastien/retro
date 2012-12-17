# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 29-Nov-2012
# Last mod  : 17-Dec-2012
# -----------------------------------------------------------------------------
# SEE:  https://exyr.org/2011/hashing-passwords/
# FROM: https://github.com/mitsuhiko/python-pbkdf2/blob/master/pbkdf2.py

import hmac, hashlib
from   struct import Struct
from   operator import xor
from   itertools import izip, starmap
from   os import urandom
from   base64 import b64encode, b64decode

_pack_int = Struct('>I').pack

# Parameters to PBKDF2. Only affect new passwords.
SALT_LENGTH = 12
KEY_LENGTH = 24
HASH_FUNCTION = 'sha256'  # Must be in hashlib.
# Linear to the hashing time. Adjust to be high but take a reasonable
# amount of time on your server. Measure with:
# python -m timeit -s 'import passwords as p' 'p.make_hash("something")'
COST_FACTOR = 100

def pbkdf2_hex(data, salt, iterations=1000, keylen=24, hashfunc=None):
	"""Like :func:`pbkdf2_bin` but returns a hex encoded string."""
	return pbkdf2_bin(data, salt, iterations, keylen, hashfunc).encode('hex')

def pbkdf2_bin(data, salt, iterations=1000, keylen=24, hashfunc=None):
	"""Returns a binary digest for the PBKDF2 hash algorithm of `data`
	with the given `salt`.  It iterates `iterations` time and produces a
	key of `keylen` bytes.  By default SHA-1 is used as hash function,
	a different hashlib `hashfunc` can be provided.
	"""
	hashfunc = hashfunc or hashlib.sha1
	mac = hmac.new(data, None, hashfunc)
	def _pseudorandom(x, mac=mac):
		h = mac.copy()
		h.update(x)
		return map(ord, h.digest())
	buf = []
	for block in xrange(1, -(-keylen // mac.digest_size) + 1):
		rv = u = _pseudorandom(salt + _pack_int(block))
		for i in xrange(iterations - 1):
			u = _pseudorandom(''.join(map(chr, u)))
			rv = starmap(xor, izip(rv, u))
		buf.extend(rv)
	return ''.join(map(chr, buf))[:keylen]

# FROM:  https://exyr.org/2011/hashing-passwords/
def encrypt(password):
	"""Generate a random salt and return a new hash for the password."""
	if isinstance(password, unicode): password = password.encode('utf-8')
	salt = b64encode(urandom(SALT_LENGTH))
	return 'PBKDF2${}${}${}${}'.format(
		HASH_FUNCTION,
		COST_FACTOR,
		salt,
		b64encode(pbkdf2_bin(password, salt, COST_FACTOR, KEY_LENGTH, getattr(hashlib, HASH_FUNCTION))))

def verify(password, encrypted):
	"""Check a password against an existing hash."""
	if isinstance(password, unicode):
		password = password.encode('utf-8')
	algorithm, hash_function, cost_factor, salt, hash_a = encrypted.split('$')
	assert algorithm == 'PBKDF2'
	hash_a = b64decode(hash_a)
	hash_b = pbkdf2_bin(password, salt, int(cost_factor), len(hash_a), getattr(hashlib, hash_function))
	assert len(hash_a) == len(hash_b)  # we requested this from pbkdf2_bin()
	# Same as "return hash_a == hash_b" but takes a constant time.
	# See http://carlos.bueno.org/2011/10/timing.html
	diff = 0
	for char_a, char_b in izip(hash_a, hash_b):
		diff |= ord(char_a) ^ ord(char_b)
	return diff == 0

def crypt_decrypt( text, password ):
	"""A simple XOR encryption, decryption"""
	# FROM :http://www.daniweb.com/software-development/python/code/216632/text-encryptiondecryption-with-xor-python
	old = StringIO.StringIO(text)
	new = StringIO.StringIO(text)
	for position in xrange(len(text)):
		bias = ord(password[position % len(password)])  # Get next bias character from password
		old_char = ord(old.read(1))
		new_char = chr(old_char ^ bias)  # Get new charactor by XORing bias against old character
		new.seek(position)
		new.write(new_char)
	new.seek(0)
	return new.read()

# EOF
