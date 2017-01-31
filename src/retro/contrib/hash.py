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

import hmac, hashlib, io
from   retro.core import unicode, IS_PYTHON3, ensureBytes, ensureString
from   struct import Struct
from   operator import xor
from   itertools import starmap
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
	if type(data) is unicode: data = data.encode()
	mac = hmac.new(data, None, hashfunc)
	def _pseudorandom(x, mac=mac):
		h = mac.copy()
		h.update(ensureBytes(x))
		if not IS_PYTHON3:
			return list(map(ord, h.digest()))
		else:
			return list(h.digest())
	buf = []
	for block in range(1, -(-keylen // mac.digest_size) + 1):
		rv = u = _pseudorandom(salt + _pack_int(block))
		for i in range(iterations - 1):
			u = _pseudorandom(''.join(map(chr, u)))
			rv = starmap(xor, zip(rv, u))
		buf.extend(rv)
	return ensureString(''.join(map(chr, buf))[:keylen])

# FIXME: This does not work in Python3!

# FROM:  https://exyr.org/2011/hashing-passwords/
def shadow(password):
	"""Generate a random salt and return a new hash for the password."""
	if isinstance(password, str): password = password.encode('utf-8')
	salt = b64encode(urandom(SALT_LENGTH))
	p    = b64encode(ensureBytes(pbkdf2_bin(password, salt, COST_FACTOR, KEY_LENGTH, getattr(hashlib, HASH_FUNCTION))))
	return 'PBKDF2${}${}${}${}'.format(
		HASH_FUNCTION,
		COST_FACTOR,
		ensureString(salt, "ascii"),
		ensureString(p,    "ascii"),
	)

def verify(password, shadow):
	"""Check a password against an existing hash."""
	password = ensureString(password)
	algorithm, hash_function, cost_factor, salt, hash_a = shadow.split('$')
	assert algorithm == 'PBKDF2'
	salt   = ensureBytes(salt)
	hash_a = b64decode(hash_a)
	hash_b = pbkdf2_bin(password, salt, int(cost_factor), len(hash_a), getattr(hashlib, hash_function))
	assert len(hash_a) == len(hash_b)  # we requested this from pbkdf2_bin()
	# Same as "return hash_a == hash_b" but takes a constant time.
	# See http://carlos.bueno.org/2011/10/timing.html
	diff = 0
	for char_a, char_b in zip(hash_a, hash_b):
		if IS_PYTHON3:
			diff |= char_a ^ ord(char_b)
		else:
			diff |= ord(char_a) ^ ord(char_b)
	return diff == 0

def crypt_decrypt( text, password, encoding="utf-8" ):
	"""A simple XOR encryption, decryption"""
	# FROM :http://www.daniweb.com/software-development/python/code/216632/text-encryptiondecryption-with-xor-python
	old = io.BytesIO(text)
	new = io.BytesIO(text)
	for position in range(len(text)):
		bias = ord(password[position % len(password)])  # Get next bias character from password
		old_char = ord(old.read(1))
		new_char = chr(old_char ^ bias)  # Get new charactor by XORing bias against old character
		new.seek(position)
		new.write(new_char)
	new.seek(0)
	return new.read()

# EOF
