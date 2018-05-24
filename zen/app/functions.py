# -*- encoding:utf-8 -*-
import os, sys, math
import sqlite3
import threading
import babel.dates
import time
import pytz
import datetime
import requests


sys.path.insert(0,os.path.abspath("../.."))

from zen import tfa, crypto
from zen.cmn import loadConfig, loadJson
from zen.chk import getBestSeed, getNextForgeRound, getNetHeight, getNodeHeight
from zen.tbw import loadTBW, spread, loadParam

def get_files_from_archive():
	payments={}
	ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
	path_to_payment = os.path.join(ROOT, "archive")
	for root, dirs, files in os.walk(path_to_payment):  
		for filename in files:
			payments[filename]=loadJson(path_to_payment+'/'+filename)
	return payments

def connect():
	if not hasattr(flask.g, "database"):
		setattr(flask.g, "database", sqlite3.connect(os.path.join(app.root_path, "..", "pay.db")))
		flask.g.database.row_factory = sqlite3.Row
	return flask.g.database.cursor()


def search(table="transaction", **kw):
	cursor = connect()
	cursor.execute(
		"SELECT * FROM %s WHERE %s=? ORDER BY timestamp DESC;"%(table, kw.keys()[0]),
		(kw.values()[0], )
	)
	result = cursor.fetchall()
	return [dict(zip(row.keys(), row)) for row in result]


def format_datetime(value, format='medium'):
	if format == 'full':
		format="EEEE, d. MMMM y 'at' HH:mm"
	elif format == 'minimal':
		format="EE dd.MM.y"
	elif format == 'medium':
		format="EE dd.MM.y HH:mm"
	#the [:-6] permits to delete the +XXYY at the end of the timestamp
	datetoparse=babel.dates.datetime.strptime(value[:-6],"%Y-%m-%d %H:%M:%S.%f")

	return babel.dates.format_datetime(datetoparse, format)
	
class ForgingService():
	
	def ForgingService(self, delegate=""):
		self.config = loadConfig()
		self.seed = getBestSeed(*self.config["seeds"])
		self.delegateParam = requests.get(self.seed+"api/delegates/get?username=%(delegate)s" % delegate).json()
		return self
	
	def epochStamp(self, d):
		t0=datetime.datetime.fromtimestamp(0,pytz.UTC) #universel time
		t1=datetime.datetime(2017, 2, 21, 13, 0, 0, 0,tzinfo=pytz.UTC)
		return (t1-t0).total_seconds() + d
	
	def delegateLastForgeBlock():
		pass
		#lastforgingblock = requests.get(self.seed+"api/blocks?limit=1&generatorPublicKey=021f277f1e7a48c88f9c02988f06ca63d6f1781471f78dba49d58bab85eb3964c6"/api/delegates/getNextForgers?limit=%(delegates)d" % kw).json().get("delegates", [])
		
	def round(self, height):
		config=loadConfig()
		activeDelegates=config['delegates']
		return math.floor(height / activeDelegates) + (1 if height % activeDelegates > 0 else 0)

	def totals(self, delegate):
		pass
	
	def getDelegateStatus(self, delegate, height):
		pass
