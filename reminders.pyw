import httplib2
import os
import time
import sqlite3 as lite
import ConfigParser
import pickle
import ctypes
import matplotlib.pyplot
import datetime
import random
import pyautogui

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

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
    PAST_WINDOW = 1 * 24 * 60 * 60
    
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Fight or Flight Reminders'
CALENDAR_ID = 'au6l05oqdrbi2g123obq0rqtos@group.calendar.google.com'
TASK_DB = 'D:\\temp\\fof_backup\\fof.db'
EVENT_DURATION = 15*60
TIME_WINDOW_SHORT = 12*60*60
NUMBER_OF_WINDOWS = 365 * 24* 60 * 60 / TIME_WINDOW_SHORT
DELAY_INIT_MAX = 60 
DELAY_INIT_POWER = 5
EVENT_REPEAT_TIMER = 30*60


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
    endtimetext = (eventtime+datetime.timedelta(seconds=EVENT_DURATION)).isoformat() + 'Z'
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
    
def isComplete(tid, timeback=0):
    if getCompletionExpirationDate(tid, timeback) > time.time() - timeback:
        return True
    else:
        return False
    
def recentTasks(timeback):
    cur.execute("SELECT taskId FROM Fights WHERE value > 0 AND endTime >= ? ORDER BY endTime DESC", [time.time()-timeback])
    try:
        return cur.fetchall()[0]
    except:
        return []
    
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

def getTaskName(tid):
    cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
    return cur.fetchall()[0][0]
    
def getTasks():
    cur.execute("SELECT DISTINCT taskId FROM Milestones WHERE deadline >= ?", [time.time()])
    tasks = [x[0] for x in cur.fetchall()]
    return tasks

def getAvgScore(tasks, start, end):
    scores = map(lambda t: getScore(t, start, end), tasks)
    return sum(scores)/len(tasks)

def chart(tasks):
    task = random.choice(list(tasks))
    times = []
    scores = []
    moment = time.time()
    while moment > time.time()-NUMBER_OF_WINDOWS*TIME_WINDOW_SHORT:
        times.append(datetime.datetime.fromtimestamp(moment))
        scores.append(getScore(task, moment-TIME_WINDOW_SHORT/2, moment+TIME_WINDOW_SHORT/2))
        moment -= TIME_WINDOW_SHORT
    scores.reverse()
    times.reverse()
    matplotlib.rc('font', family='Arial')
    matplotlib.pyplot.plot(times, scores, 'ko:', label = unicode(getTaskName(task)))
    matplotlib.pyplot.legend(loc='best')
    matplotlib.pyplot.show()
    
def durationToText(seconds, strict=False):
    negative = False
    if seconds < 0:
        negative = True
        seconds = -seconds
    days, remainder = divmod(seconds, 24*60*60)
    hours, remainder = divmod(remainder, 60*60)
    minutes, seconds = divmod(remainder, 60)
    timeString = '-' if negative else ''
    timeString += str(int(days))+':' if (strict or days > 0) else ''
    timeString += ('0' if strict or (days > 0 and hours < 10) else '') + str(int(hours))+':' if (strict or days > 0 or hours > 0) else ''
    timeString += ('0' if (strict or ((hours > 0 or days > 0) and minutes < 10)) else '') + str(int(minutes))
    return unicode(str(seconds)+"''" if timeString == '0' else timeString)

con = lite.connect(TASK_DB)
cur = con.cursor()               
tasks = set(getTasks())
found = filter(lambda t: not isComplete(t), tasks)
    
avgScore = getAvgScore(tasks, time.time()-TIME_WINDOW_SHORT/2, time.time()+TIME_WINDOW_SHORT/2)
delay = int(DELAY_INIT_MAX * avgScore**DELAY_INIT_POWER)
if not found:
    closestCompletionDate = min(map(getCompletionExpirationDate, tasks))
    delay += max( int(closestCompletionDate - time.time()), EVENT_REPEAT_TIMER )
for _ in range(len(found)): pyautogui.hotkey('alt', 'f4')
#os.system("shutdown -s -t " + str(delay))
if delay < DELAY_INIT_MAX:
    found.sort(key=getCompletionExpirationDate, reverse=True)
    ctypes.windll.user32.MessageBoxW(0, "\n".join(map(getTaskName, found)), str(int(100*avgScore))+u'%', 0)
if random.randint(1,100) == 1:
    chart(tasks)

con.close()