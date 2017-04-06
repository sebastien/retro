import os, json, logging, retro.core
try:
	import urllib.request as urllib_request
except ImportError:
	try:
		import urllib3.request as urllib_request
	except ImportError, e:
		import urllib as urllib_request


class Robots:

	DB      = None
	DB_PATH = os.path.dirname(os.path.abspath(__file__)) + "/robots.json"

	@classmethod
	def EnsureDB( cls, path=None ):
		path = path or cls.DB_PATH
		if not cls.DB:
			if not os.path.exists(path):
				cls.DB = cls.SaveDB(path, cls.ImportDB())
			else:
				with open(path) as f:
					cls.DB = json.load(f)
		return cls.DB

	@classmethod
	def SaveDB( cls, path=None, db=None ):
		db   = db   or cls.EnsureDB()
		path = path or cls.DB_PATH
		with open(path, "wb") as f:
			json.dump(db, f)
		return db

	@classmethod
	def ImportDB( cls, url="http://www.robotstxt.org/db/all.txt", encoding="latin-1"):
		f  = urllib_request.urlopen(url)
		db_full   = {}
		robot_id = None
		for i, l in enumerate(f.readlines()):
			try:
				l.decode(encoding)
			except UnicodeDecodeError as e:
				logging.error("retro.contrib.agents.Robots.ImportDB: Cannot decode line {0}:{1}".format(i,repr(l)))
				continue
			if l.startswith("robot-id:"):
				robot_id = l.split(":",1)[1].strip()
			if l.startswith("robot-useragent:"):
				robot_ua = l.split(":",1)[1].strip()
				try:
					if robot_ua:
						robot_ua = robot_ua.encode("ascii")
						db_full[robot_ua] = robot_id

				except UnicodeDecodeError as e:
					logging.error("retro.contrib.agents.Robots.ImportDB: User agent is not ascii at line {0}:{1}".format(i,repr(robot_ua)))
					continue
		return db

	@classmethod
	def Detect( cls, request ):
		if isinstance(request, retro.core.Request): user_agent = request.userAgent()
		else: user_agent = request
		db = cls.EnsureDB()
		return user_agent in db

class NoScript:

	AGENTS = [
		"BinGet",
		"cURL",
		"curl",
		"Java",
		"libwww-perl",
		"Microsoft URL Control",
		"Peach",
		"PHP",
		"pxyscand",
		"PycURL",
		"Python-urllib",
		"Wget",
		"Elinks",
		"w3m",
	]

	@classmethod
	def Detect( cls, request ):
		if isinstance(request, retro.core.Request): user_agent = request.userAgent()
		else: user_agent = request
		for a in cls.AGENTS:
			if user_agent.startswith(a):
				return True
		return Robots.Detect(request)

# EOF
