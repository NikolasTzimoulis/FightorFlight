import time
import sqlite3 as lite
import ctypes
import matplotlib.pyplot
import datetime
import random
import win32gui, win32process
import os
import signal
import pyautogui 

TASK_DB = 'D:\\temp\\fof_backup\\fof.db'
pyautogui.FAILSAFE = False

TIME_WINDOW_SHORT = 12*60*60
NUMBER_OF_WINDOWS = 365 * 24* 60 * 60 / TIME_WINDOW_SHORT
RECENT_SAMPLES = 10
MAX_VARIANCE = 0.25
LOCK_PER_FOUND = 20
    
def isRunning(tid):
    cur.execute("SELECT endTime FROM Fights WHERE value = 0 AND taskId = ? ORDER BY endTime DESC LIMIT 1", [tid])
    try:
        if cur.fetchall()[0][0] > time.time():
            return True
    except:
        pass
    return False
    
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
    if abs(sum(scores[-RECENT_SAMPLES:])/RECENT_SAMPLES-scores[-1]) > MAX_VARIANCE:
        matplotlib.rc('font', family='Arial')
        matplotlib.pyplot.plot(times, scores, 'ko:', label = unicode(getTaskName(task)))
        matplotlib.pyplot.legend(loc='best')
        matplotlib.pyplot.show()
        return True
    return False

    

con = lite.connect(TASK_DB)
cur = con.cursor()               
tasks = set(getTasks())
found = filter(lambda t: not (isComplete(t) or isRunning(t)), tasks)
myPid = os.getpid()
    
avgScore = getAvgScore(tasks, time.time()-TIME_WINDOW_SHORT/2, time.time()+TIME_WINDOW_SHORT/2)
found.sort(key=getCompletionExpirationDate, reverse=True)
messageTitle = str(int(100*avgScore))+u'%'
messageBody = "\n".join(map(getTaskName, found))

if found:
    for _ in found:
        handle = win32gui.GetForegroundWindow()
        threadid,pid = win32process.GetWindowThreadProcessId(handle)
        print win32gui.GetWindowText(handle)
        if not pid == myPid: os.system("taskkill /pid " + str(pid))
        pyautogui.hotkey("alt", "esc")        
        time.sleep(1)
    pyautogui.hotkey("win", "m")

    unlockTime = time.time() + LOCK_PER_FOUND * len(found)
    while time.time() < unlockTime:     
        ctypes.windll.user32.LockWorkStation()
        time.sleep(1)

    if not chart(found):
        con.close()
        ctypes.windll.user32.MessageBoxW(0, messageBody, messageTitle, 0)