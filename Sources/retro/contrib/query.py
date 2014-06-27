# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 27-Nov-2012
# Last mod  : 17-Dec-2012
# -----------------------------------------------------------------------------

import re

RE_DATE = re.compile("(\d\d\d\d)/?(\d\d|\w+)?/?(\d\d)?[/T]?(\d\d)?[:h]?(\d\d)?[:m]?(\d\d)?s?")
#                       Y Y Y Y  M  M  M     D D    H H   M M    S S
def asAndOrList(text, union=",", intersection=" ", transform=lambda _:_):
	"""Ensures that the given text which can be separated by union (or)
	and intersection (and) delimiters is return as a list of AND lists,
	in the following style:

	```(a AND b) or (c) or (d AND e AND f)```

	This data structure is used as the base for expressing all the queries in
	this module.
	"""
	# NOTE: In URLs, the + is translated to space!
	res = []
	if isinstance(text, str): text = (text,)
	for keywords in text:
		for union_keywords in keywords.split(union):
			# NOTE: Should support QUOTING
			res.append(list(map(transform, union_keywords.split(intersection))))
	return res

# -----------------------------------------------------------------------------
#
# QUERY PREDICATE
#
# -----------------------------------------------------------------------------

class QueryPredicate:
	"""An abstract class that defines how to parse, match and compare a value
	to an expected value"""

	def __init__( self ):
		pass

	def parse( self, value ):
		"""Converts the value represented as a string to a value in the
		property format. May throw a `ValueError`."""
		raise NotImplemented

	def match( self, expected, compared ):
		"""Tells if the `compared` value matches the `expected` value. This
		can return either a boolean or a number indicating the distance between
		both values."""
		return expected == compared

	def compare( self, expected, compared ):
		"""Compares the given values, should follow the same conventions as
		the `cmp` function."""
		return cmp(expected,compared)

	def __call__( self, value ):
		"""Calls `self.parse(value)`"""
		return self.parse(value)

# -----------------------------------------------------------------------------
#
# QUERY SAME
#
# -----------------------------------------------------------------------------

class QuerySame(QueryPredicate):
	"""Tells if the values are the same"""

	def parse( self, value ):
		return value

# -----------------------------------------------------------------------------
#
# QUERY INT
#
# -----------------------------------------------------------------------------

class QueryInt(QueryPredicate):
	"""Compares integers"""

	def parse( self, value ):
		while len(data) > 1 and data[0] == "0": data = data[1:]
		return int(data)

# -----------------------------------------------------------------------------
#
# QUERY STRING
#
# -----------------------------------------------------------------------------

class QueryString(QueryPredicate):
	"""Compares strings (case-insensitive)"""

	def parse( self, value ):
		return str(data).strip().lower()

# -----------------------------------------------------------------------------
#
# QUERY SUB-STRING
#
# -----------------------------------------------------------------------------

class QuerySubString(QueryPredicate):
	"""Compares sub-strings (case-insensitive)"""

	def parse( self, value ):
		return str(data).strip().lower()

	def match( self, expected, compared ):
		return compared.find(expected) > 0

# -----------------------------------------------------------------------------
#
# QUERY DATE
#
# -----------------------------------------------------------------------------

class QueryDate(QueryPredicate):
	"""Compares dates, expected in `YYYYMMDDHHMMSS` string format"""

	def parse( self, value ):
		"""Expects YYYYMMDDHHMMSS"""
		data    = RE_DATE.match(data)
		year    = cls.INT(data.group(1) or "0")
		month   = cls.INT(data.group(2) or "0")
		day     = cls.INT(data.group(3) or "0")
		hour    = cls.INT(data.group(4) or "0")
		minute  = cls.INT(data.group(5) or "0")
		seconds = cls.INT(data.group(6) or "0")
		return (year, month, day, hour, minute, seconds)


# -----------------------------------------------------------------------------
#
# QUERY RANGE
#
# -----------------------------------------------------------------------------

class QueryRange(QueryPredicate):
	"""Queries a range, expressed as `I-J`"""

	def __init__( self, queryType ):
		QueryPredicate.__init__(self)
		self.queryType = queryType

	def parse( self, value ):
		data = data.split("-")
		if len(data) == 1:
			return (queryType.parse(data[0]),None)
		else:
			return (queryType.parse(data[0]),queryType.parse(data[1]))

# -----------------------------------------------------------------------------
#
# QUERY
#
# -----------------------------------------------------------------------------

class Query:
	"""Abstracts a query object that can be run on an iterator, yielding the
	results that match the predicate defined in the query."""

	INT       = QueryInt
	SAME      = QuerySame
	STRING    = QueryInt
	SUBSTRING = QueryInt
	DATE      = QueryDate
	RANGE     = QueryRange

	@classmethod
	def Parse( cls, query, format=None ):
		"""Parses a query given as the a dictionary of strings using the given
		format. For instance

		>    query  = dict(date=("20121011", "20121010", "20121009") ,articlesCount="0-100",)
		>    format = dict(date=Query.DATE, articlesCount=Query.RANGE)

		Note that `query` values will be passed through the `asAndOrList` and
		should be in the AND OR list format (ie. ((A and B and C) or (A' and B' and C'))).
		"""
		result = {}
		for key in format:
			if key in query:
				result[key] = [list(map(format[key],_)) for _ in (asAndOrList(query[key]))]
		return result

	def __init__( self, query, format=None ):
		"""Creates a new query instance from the given `query` dictionary parsed in the given
		`format`. See  `Query.Parse` for more details."""
		if format: query = self.Parse(query, format)
		self.query = query

	def predicate( self, value ):
		"""Tells if the given value (given as a dictionary) matches the given query
		predicates."""
		for key in list(self.query.keys()):
			expected = query[key]
			element  = expected[0][0]
			# Each Query.[RANGE|NORMALIZED|etc] should return an object that
			# implements a `match`
			# FIXME: Support DATE
			# FIXME: Support RANGE
			# FIXME: Support SUBSTRING
			# FIXME: Support STRING
			if not hasattr(value, key): return False
			elif not self.matchSubstring(expected, getattr(value, key)): return False
		return True

	def run(self, iterator, predicate=None, skip=None, count=-1, sort=None, order=-1):
		"""Runs the query on the given set of results (as an iterator), skipping
		elements and returning only count elements."""
		predicate = predicate or self.predicate
		if sort:
			iterator = list(iterator)
			iterator = sorted(iterator, key=sort, reverse=order < 0)
		i      = 0
		iterator = list(iterator)
		# DEBUG:
		# print "RUNNING QUERY len=%s skip=%s count=%s sort=%s order=%s" % ( len(iterator), skip, count, sort, order)
		for value in iterator:
			if not predicate(self, value):
				continue
			if skip != None and skip > 0:
				skip -= 1
			else:
				yield value
				i += 1
			if (count > 0) and (i >= count):
				break

	def matchSubstring( self, expected, *compared ):
		return self._match(lambda e,c:e.find(c)!=-1, expected, compared )

	# if it's just A, then you need to give [[A]]
	def _match( self, predicate, expected, compared ):
		"""Returns true if it finds ANY of the elements of expected in ANY
		of the elements of the compared list.

		Expected is a list of lists, such as

		>    [ [A], [B,C], [D] ]

		would translate in

		>    (A) or (B and C) or (D)

		"""
		# If nothing is expected, then we return True
		if not expected: return True
		# If nothing is compared, then we return False
		# (although this will break if None or "" is in expected.
		if not compared: return False
		# For value that is compared
		for value in compared:
			# For each AND-joined expected values
			for e_and in expected:
				matched = True
				assert e_and != None
				for e in self._ensureList(e_and):
					# As soon as an AND-join expected does not match, we break
					# note: the `value is None` is here for protection from
					# failing predicates
					if value is None or not predicate(e, value):
						matched = False
						break
				# As soon as one of the AND-join expected list matches, we
				# can safely return
				if matched:
					return True
		return False

	def _ensureList( self, value ):
		if value is None:
			return ()
		elif type(value) not in (tuple, list):
			return (value,)
		else:
			return value

# EOF
