import re

RE_DATE = re.compile("(\d\d\d\d)/?(\d\d|\w+)?/?(\d\d)?[/T]?(\d\d)?[:h]?(\d\d)?[:m]?(\d\d)?s?")
#                       Y Y Y Y  M  M  M     D D    H H   M M    S S
def asAndOrList(text, union=",", intersection=" ", transform=lambda _:_):
	"""Ensures that the given text which can be separated by union (or)
	and intersection (and) delimiters is return as a list of AND lists,
	in the following style:
	
	(a AND b) or (c) or (d AND e AND f)

	"""
	# NOTE: In URLs, the + is translated to space!
	res = []
	if type(text) in (unicode,str): text = (text,)
	for keywords in text:
		for union_keywords in keywords.split(union):
			# NOTE: Should support QUOTING
			res.append(map(transform, union_keywords.split(intersection)))
	return res

class QueryType:

	def __init__( self ):
		pass

	def parse( self, value ):
		raise NotImplemented

	def match( self, expected, compared ):
		return expected == compared

	def compare( self, expected, compared ):
		return cmp(expected,compared)

	def __call__( self, value ):
		return self.parse(value)

class QuerySame(QueryType):

	def parse( self, value ):
		return value

class QueryInt(QueryType):

	def parse( self, value ):
		while len(data) > 1 and data[0] == "0": data = data[1:]
		return int(data)

class QueryString(QueryType):

	def parse( self, value ):
		return unicode(data).strip().lower()

class QuerySubString(QueryType):

	def parse( self, value ):
		return unicode(data).strip().lower()

	def match( self, expected, compared ):
		return compared.find(expected) > 0

class QueryDate(QueryType):

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

class QueryRange(QueryType):

	def __init__( self, queryType ):
		QueryType.__init__(self)
		self.queryType = queryType

	def parse( self, value ):
		data = data.split("-")
		if len(data) == 1:
			return (queryType.parse(data[0]),None)
		else:
			return (queryType.parse(data[0]),queryType.parse(data[1]))

class Query:

	INT       = QueryInt
	SAME      = QuerySame
	STRING    = QueryInt
	SUBSTRING = QueryInt
	DATE      = QueryDate
	RANGE     = QueryRange

	@classmethod
	def Parse( cls, query, format=None ):
		"""Parses a query ... """
		result = {}
		for key in format:
			if key in query:
				result[key] = map(lambda _:map(format[key],_), (asAndOrList(query[key])))
		return result

	def __init__( self, query, format=None ):
		if format: query = self.Parse(query, format)
		self.query = query
	
	def predicate( self, value ):
		for key in self.query.keys():
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

	def matchRegexp( self, expected, *compared ):
		return self._match(lambda e,c:e.search(c)!=None, expected, compared )

	def matchSubstring( self, expected, *compared ):
		return self._match(lambda e,c:e.find(c)!=-1, expected, compared )
	
	def matchElement( self, expected, *compared ):
		assert not filter(lambda _:_ and len(_) > 1, expected or ()), "It does not make sense to match elements with AND: %s" % (expected)
		return self._match(lambda e,c:e == c, expected, compared )

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
