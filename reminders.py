import httplib2
import os
import time
import sqlite3 as lite
import ConfigParser

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

import datetime

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None
configFileName = "config.ini"
config = ConfigParser.ConfigParser()
try:
    config.read(configFileName)
    PAST_WINDOW = config.getint(config.sections()[0], "pastshown") * 24 * 60 * 60
except:
    print "Could not load config file. Reverting to default values."
    PAST_WINDOW = 30 * 24 * 60 * 60
    
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Calendar API Quickstart'
CALENDAR_ID = 'au6l05oqdrbi2g123obq0rqtos@group.calendar.google.com'
TASK_DB = 'fof.db'
DEFAULT_SLEEP_TIME = 60*60
PAD_TIME = 60
ACCEPTABLE_DELAY = 0 #24 * 60 * 60



def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'calendar-quickstart.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatability with Python 2.6
            credentials = tools.run(flow, store)
        print 'Storing credentials to ' + credential_path
    return credentials

def createEvent(title, startTime, endTime):
    return {
  'summary': title,
  'location': '',
  'description': '',
  'start': {
    'dateTime': startTime,
    'timeZone': '',
  },
  'end': {
    'dateTime': endTime,
    'timeZone': '',
  },
  'recurrence': [],
  'attendees': [],
  'reminders': {
    'useDefault': True,
    'overrides': [],
  },
}

def addEvent(title, eventtime):
    """Shows basic usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs a list of the next
    10 events on the user's calendar.
    """
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)
    starttimetext = eventtime.isoformat() + 'Z'
    endtimetext = (eventtime+datetime.timedelta(seconds=DEFAULT_SLEEP_TIME-PAD_TIME)).isoformat() + 'Z'
    event = createEvent(title, starttimetext, endtimetext)
    #print service.calendarList().list(pageToken=None).execute()
    event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    
def getCompletionExpirationDate(tid, timeback=0):
    cur.execute("SELECT value, endTime FROM Fights WHERE taskId = ? AND value > 0 AND endTime <= ? ORDER BY endTime DESC LIMIT 1", [tid, time.time()-timeback])
    try:
        result = cur.fetchall()[0]
        return result[0]+result[1]
    except:
        return -float("inf")
    
def getScore(tid, start, end):
    cur.execute("SELECT startTime, endTime, value FROM Fights WHERE taskID = ? AND value > 0 AND endTime+value >= ? AND startTime <= ?", [tid, start, end])
    rows = cur.fetchall()
    
    # sum running duration and completion time for tasks in this time period
    score = sum([x[1]-x[0]+x[2] for x in rows])
    # stretch time period duration so that edge tasks don't inflate the score
    try: actualStart = min ( start ,  min([x[0] for x in rows]) )
    except: actualStart = start
    try: actualEnd = max ( end,  max([x[1]+x[2] for x in rows]) )
    except: actualEnd = end 
    
    if score == (actualEnd-actualStart): return 1.0
    return score/(actualEnd-actualStart)

def getRunningTasks():
    cur.execute("SELECT taskId FROM Fights WHERE value = 0 AND endTime > ?", [time.time()])
    rows = cur.fetchall()
    return map(lambda x: x[0], rows)

def getSleepTime():
    cur.execute("SELECT endTime FROM Fights WHERE value = 0 AND endTime > ? ORDER BY endTime DESC LIMIT 1", [time.time()])
    rows = cur.fetchall()
    if rows and rows[0][0] > time.time()+DEFAULT_SLEEP_TIME:
        return rows[0][0]-time.time()
    else:
        return DEFAULT_SLEEP_TIME

def getTaskName(tid):
    cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
    return cur.fetchall()[0][0]
    
def getTasks():
    cur.execute("SELECT DISTINCT taskID FROM Fights WHERE value > 0 AND endTime >= ?", [time.time() -  PAST_WINDOW])
    tasks = [x[0] for x in cur.fetchall()]
    tasks = filter(lambda t: time.time()-getCompletionExpirationDate(t)>ACCEPTABLE_DELAY, tasks)
    return tasks

shown = set()
print datetime.datetime.now().strftime('%H:%M'),
while True:
    con = lite.connect(TASK_DB)
    cur = con.cursor()               
    tasks = set(getTasks())
    if tasks-shown:
        tasks -= shown
    else:
        shown = set()
    if tasks and not getRunningTasks():
        focus = max(tasks, key=lambda t: getScore(t, time.time() -  PAST_WINDOW, time.time()))
        shown.add(focus)
        remindertime = datetime.datetime.utcnow()
        addEvent(getTaskName(focus), remindertime)
        print getTaskName(focus)
    else:
        print
        shown = set()
    sleepTime = getSleepTime()
    print (datetime.datetime.now()+datetime.timedelta(seconds=sleepTime)).strftime('%H:%M'),
    con.close()
    time.sleep(sleepTime)