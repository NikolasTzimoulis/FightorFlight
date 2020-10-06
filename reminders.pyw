#! python2
# -*- coding: utf-8 -*-
import time
import datetime
import sqlite3 as lite
import matplotlib.pyplot
#import matplotlib.axis
import os
import winsound
import subprocess
import random

#TASK_DB = 'D:\\temp\\fof_backup\\fof.db'
TASK_DB = 'fof.db'
#pyautogui.FAILSAFE = False

TIME_WINDOW_SHORT = 7*24*60*60
NUMBER_OF_WINDOWS = 365 * 24* 60 * 60 / TIME_WINDOW_SHORT
WAYPOINTS = [0.95, 0.75, 0.5, 0.25, 0.0]
LOCK_PER_FOUND = 1
LOCK_AT_FINAL = 9
FINAL_FRACTION = 60
CIRCLES = [u'\u2588', u'\u2586', u'\u2584', u'\u2582', u'\u2581']
COLOURS = ['k', 'b', 'g', 'r', 'c', 'm', 'y']
SOUNDFILES = ["Radiant_Horn.wav", "43_Ocarina_-_Song_of_Time.wav", "01. Prologue.wav", "30. The Beast is Upon Me.wav", "73. The Woodsman's Lantern.wav", "temple_window_panel_open_4.sound.wav"]
MOTTOS=[""]
MOTTO_TIME = 10800
EXCUSESFILE = r"C:\Users\Nikolas\Desktop\excuses.txt"
EDITOREXE = r"C:\Program Files (x86)\Notepad++\notepad++.exe"
FOCUS_TASK = -1
    
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

def getPledgesTotalDuration(tid, start, end):
    cur.execute("SELECT SUM(endTime-startTime) FROM Fights WHERE TaskID = ? AND endTime+value >= ? AND startTime <= ?", [tid, start, end])
    seconds = cur.fetchall()[0][0]
    return int(round(seconds/60/60)) if seconds is not None else 0


def getTaskName(tid):
    cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
    return cur.fetchall()[0][0]
    
def getTasks():
    cur.execute("SELECT DISTINCT taskId FROM Milestones WHERE deadline >= ?", [time.time()])
    tasks = [x[0] for x in cur.fetchall()]
    return tasks

def getLastPledge(tid):
    cur.execute("SELECT startTime FROM Fights WHERE TaskID = ? ORDER BY startTime DESC LIMIT 1", [tid])
    return cur.fetchall()[0][0]

def pickSound(count):
    if count > 0:
        soundfile = SOUNDFILES[min(count-1, len(SOUNDFILES)-1)]
        winsound.PlaySound(soundfile, winsound.SND_ASYNC | winsound.SND_FILENAME)

def getAvgScore(tasks, start, end):
    scores = map(lambda t: getScore(t, start, end), tasks)
    return sum(scores)/len(tasks)

def sleepShutdown():
    shutDownTime = max(now+60, (getCompletionExpirationDate(4) * 0.25 + (getLastPledge(4) + 86400) * 0.75))
    #print "ideal:", datetime.datetime.fromtimestamp(getCompletionExpirationDate(4)).strftime('%Y-%m-%d %H:%M:%S')
    #print "last:", datetime.datetime.fromtimestamp(getLastPledge(4)).strftime('%Y-%m-%d %H:%M:%S')
    #print "target:", datetime.datetime.fromtimestamp(shutDownTime).strftime('%Y-%m-%d %H:%M:%S')
    secondsLeft = int(shutDownTime - now)
    os.system("shutdown /s /t " + str(secondsLeft) + " > nul 2>&1")
    
def writeExcuse(tid):    
    if time.time() - getCompletionExpirationDate(tid) > 60*60 and random.random() > 0.9:
        tname = getTaskName(tid)
        opening = (datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d, %H:%M') + "\n\t" + tname + ": \n").encode('utf-8')
        f = open(EXCUSESFILE, "r")
        contents = f.readlines()
        f.close()
        contents.insert(0, opening)
        f = open(EXCUSESFILE, "w")
        contents = "".join(contents)
        f.write(contents)
        f.close()
        p = subprocess.Popen([EDITOREXE, EXCUSESFILE])
        returncode = p.wait() 
    
def chart(task, colour, title):
    times = []
    scores = []
    pledges = []
    moment = time.time()
    while moment > time.time()-NUMBER_OF_WINDOWS*TIME_WINDOW_SHORT:
        times.append(moment)
        scores.append(100*getScore(task, moment-TIME_WINDOW_SHORT, moment))
        pledges.append(getPledgesTotalDuration(task, moment-TIME_WINDOW_SHORT, moment))
        moment -= TIME_WINDOW_SHORT
    while scores[-1]==0 and len(scores)>1: 
        scores.pop()
    times = times[:len(scores)]
    pledges = pledges[:len(scores)]
    scores.reverse()
    times.reverse()
    pledges.reverse()
    avgScore = 100*getScore(task, times[0], time.time())
    matplotlib.pyplot.figure(0).canvas.set_window_title(title)
    matplotlib.pyplot.get_current_fig_manager().window.state('zoomed')
    matplotlib.rc('font', family='Arial')
    style = colour+'o:'
    times2 = map(datetime.datetime.fromtimestamp, times)
    matplotlib.pyplot.plot(times2, scores, style, markersize = 15, label = unicode(getTaskName(task)))
    matplotlib.pyplot.gca().yaxis.set_label_position('right') 
    matplotlib.pyplot.legend(loc='upper left')
    matplotlib.pyplot.ylim(0, 100)
    matplotlib.pyplot.xlim(min(times2), datetime.datetime.fromtimestamp(max(times)+2*TIME_WINDOW_SHORT))
    matplotlib.pyplot.axhline(y=avgScore, color=colour, )
    axes = matplotlib.pyplot.figure(0).get_axes()
    ax2 = axes[0].twinx()
    ax2.plot(times2, scores, '', visible=False)
    matplotlib.pyplot.ylim(0, 100)
    matplotlib.pyplot.xlim(min(times2), datetime.datetime.fromtimestamp(max(times)+2*TIME_WINDOW_SHORT))
    if abs(round(avgScore) - round(scores[-1])) > 1:
        ax2.set_yticks([round(avgScore), round(scores[-1])])
    else:
        ax2.set_yticks([round(avgScore)])
    spacer = (max(times)-min(times))/350 
    for t, s, p in zip(times, scores, pledges):
        matplotlib.pyplot.text(datetime.datetime.fromtimestamp(t-(spacer if p < 10 else 2*spacer)), s-0.5, p, color="white", fontsize=11)
    matplotlib.pyplot.draw() 
    matplotlib.pyplot.get_current_fig_manager().window.attributes('-topmost', 1)



con = lite.connect(TASK_DB)
cur = con.cursor()               
tasks = set(getTasks())
found = filter(lambda t: not (isComplete(t) or isRunning(t)), tasks)
#found = list(tasks)
myPid = os.getpid()
now = time.time()

avgScore = getAvgScore(tasks, time.time()-TIME_WINDOW_SHORT, time.time())
found.sort(key=lambda t: 1 if t==FOCUS_TASK else getScore(t, now-TIME_WINDOW_SHORT, now), reverse=False)
messageTitle = str(int(100*avgScore))+u'%'
for i in range(len(WAYPOINTS)):
    if avgScore >= WAYPOINTS[i]:
        messageTitle += ' '+CIRCLES[i]
        break
messageTitle += '     (' + ", ".join(map(getTaskName, found)) + ')'


pickSound(len(found))
for task in found:
    #print task, getTaskName(task)
    colour = COLOURS[task%len(COLOURS)]
    if not task == found[-1]:
        unlockTime = time.time() + LOCK_PER_FOUND
    else:
        timeDelayed = max(time.time() - getCompletionExpirationDate(task), 0)
        unlockTime =  time.time() + LOCK_AT_FINAL + timeDelayed/FINAL_FRACTION
        if timeDelayed > MOTTO_TIME:
            messageTitle = random.choice(MOTTOS)
    while time.time() < unlockTime:
        chart(task, colour, messageTitle)
        try: 
            matplotlib.pyplot.pause(1)
            matplotlib.pyplot.clf()
        except: pass    
    #winsound.Beep(frequency, SOUND_DURATION)
    #print frequency, getTaskName(task)
    #frequency = int(frequency*FREQUENCY_FACTOR)
#writeExcuse(found[-1])

if not isComplete(4):
    sleepShutdown()