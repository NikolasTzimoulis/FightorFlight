from Tkinter import *
import ttk
import sqlite3 as lite
import time
import ConfigParser
import os
import winsound
import datetime
import matplotlib.pyplot
import tkFont

taskDB = "fof.db"
soundPlaylist = "sounds.m3u"
configFileName = "config.ini"
config = ConfigParser.ConfigParser()
try:
    config.read(configFileName)
    pastshown = config.getint(config.sections()[0], "pastshown")
    proposalWaitTime = config.getint(config.sections()[0], "proposalwaittime") * 1000 * 60
    quickInfoWaitTime = config.getint(config.sections()[0], "quickinfowaittime") * 1000
    defaultCompletionExpiration = config.getint(config.sections()[0], "defaultcompletionexpiration")
    historyGraphLength = config.getint(config.sections()[0], "historygraphlength")
except:
    print "Could not load config file. Reverting to default values."
    pastshown = 1
    proposalWaitTime = 60 * 60 * 1000
    quickInfoWaitTime = 5 * 1000
    defaultCompletionExpiration = 12
    historyGraphLength = 10
duration = [1, 7, 30, 90, 365, float("inf")]
suggestionSkips = -1
clockStrings = {}
activeTasks = []
lastReloadTime = 0
lastSuggestion = None
quickInfoReset = None
nextMainReload = None

def addNewTask(_):
    line = entryText.get()
    if len(line) > 0 and line.split()[0].isalpha() and line.split()[-1].isdigit():
        cur.execute("SELECT id FROM Tasks WHERE name = ?", [ " ".join(line.split()[:-1]) ])
        rows = cur.fetchall()
        if len(rows) > 0:
            tid = rows[0][0]
        else:
            cur.execute("INSERT INTO Tasks(name) VALUES(?)", [ " ".join(line.split()[:-1]) ])
            con.commit()
            cur.execute("SELECT id FROM Tasks WHERE name = ?", [ " ".join(line.split()[:-1]) ])
            tid = cur.fetchall()[0][0]
        cur.execute("UPDATE Fights SET value=-1 WHERE taskId=? AND value = 0 AND startTime <= ?;", [tid, time.time()])
        cur.execute("UPDATE Tasks SET complete = ? WHERE complete > ? AND id=?", [time.time(), time.time(), tid])
        cur.execute("INSERT INTO Fights VALUES(?, ?, ?, ?)", [time.time(), time.time()+int(line.split()[-1])*60, 0, tid])
        con.commit() 
        entryText.set("")
        root.after(1, reloadMain)

def resolveFight(task_id, timeStart, timeEnd, value):
    def resolveFight_inner(_=None):
        cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [value, task_id, timeStart, timeEnd])
        con.commit()
        if value == 1:
            playAudio(soundFiles[3])
        elif value == -1:
            rescheduleFight(task_id, timeStart, timeEnd)(None)     
            playAudio(soundFiles[2])
        root.after(1, reloadMain)   
    return resolveFight_inner        


def periodicProposal():
    global suggestionSkips, proposalWaitTime, activeTasks
    suggestionSkips = -1
    if len(activeTasks) == 0:
        proposeTask(beepThreshold = duration[pastshown])
    else:
        proposeTask()
    root.after(proposalWaitTime, periodicProposal)

        
def getCountdownString(deadline):
    timeLeft = deadline - time.time() 
    daysLeft = int((timeLeft)/60/60/24)
    hoursLeft = int((timeLeft)/60/60 - daysLeft*24) 
    minutesLeft = int((timeLeft)/60 - daysLeft*24*60 - hoursLeft*60)
    secondsLeft = int(timeLeft - daysLeft*24*60*60 - hoursLeft*60*60 - minutesLeft*60)
    timeString = ("-" if timeLeft<0 else "") 
    timeString += (str(abs(daysLeft))+":") if daysLeft != 0 else ""
    timeString += (("0" if abs(hoursLeft)<10 else "") + str(abs(hoursLeft))+":") if (hoursLeft != 0 or daysLeft !=0) else ""
    timeString += ("0" if abs(minutesLeft)<10 else "") + str(abs(minutesLeft))+":"
    timeString += ("0" if abs(secondsLeft)<10 else "") + str(abs(secondsLeft))
    return timeString

def changePastShown(step):
    def changePastShown_inner(_=None):
        global pastshown
        pastshown = (pastshown+step)%len(duration) 
        config.set(config.sections()[0], "pastshown", pastshown)    
        root.after(1, reloadMain)
    return changePastShown_inner   
         
def proposeTask(skipChange = 0, beepThreshold = 0):
    global suggestionSkips, activeTasks
    suggestionSkips += skipChange
    if suggestionSkips < 0: suggestionSkips = 0
    found = False
    days = 0
    skipsLeft = suggestionSkips
    window = 60*60
    while not found and days <= duration[-2]:
        days += 1
        pastDate = time.time() - days * 24 * 60 * 60
        cur.execute("SELECT taskId, startTime, endTime FROM Fights WHERE value = 1 AND startTime < ? AND endTime > ? ORDER BY startTime ASC", [pastDate+window, pastDate-window])
        rows = cur.fetchall()
        for fight in rows:
            if fight[0] in activeTasks or isComplete(fight[0]):
                continue
            elif skipsLeft > 0:
                skipsLeft -= 1
                continue
            else:
                found = True
                rescheduleFight(fight[0], fight[1], fight[2])(None)
                if days <= beepThreshold:
                    playAudio(soundFiles[0])
                break
    
def rescheduleFight(tid, timestamp, deadline, reload=False):
    def rescheduleFight_inner(_):
        global lastSuggestion, quickInfoWait, quickInfoReset
        entryText.set(generateTaskText(tid, timestamp,deadline))
        lastSuggestion = (tid, timestamp, deadline)
        quickInfoText.set(getDateString(deadline))
        if quickInfoReset is not None: root.after_cancel(quickInfoReset)
        quickInfoReset = root.after(quickInfoWaitTime, lambda: quickInfoText.set(''))    
        if reload: root.after(1, reloadMain)    
    return rescheduleFight_inner

def generateTaskText(tid, timestamp, deadline):
    return getTaskName(tid)+" "+str(int(round((deadline-timestamp)/60)))

def getDateString(deadline):
    try:
        return datetime.datetime.fromtimestamp(deadline).strftime('%Y-%m-%d, %H:%M')
    except:
        return num2str(deadline)

def getTaskName(tid):
    cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
    return cur.fetchall()[0][0]

def showHistory(tid):
    def showHistory_inner(_):
        end = time.time()
        period = 0
        history = []        
        #while end >= time.time() - getRealDuration(duration[pastshown+1]) * 24 * 60 * 60:
        for _ in range(historyGraphLength):
            end = time.time() - period * duration[pastshown] * 24 * 60 * 60
            start = time.time() -  (period+1) * duration[pastshown] * 24 * 60 * 60
            cur.execute("SELECT COUNT(*) FROM Fights WHERE taskID = ? AND value = 1 AND endTime >= ? AND endTime <= ?", [tid, start, end])
            history.append(cur.fetchall()[0][0])
            period += 1
        matplotlib.pyplot.clf()
        matplotlib.pyplot.plot(history[::-1], 'ro-')
        matplotlib.pyplot.show()
    return showHistory_inner

def showTasks(completed=False):
    def showTasks_inner(_):
        startingDate = time.time() -  duration[pastshown] * 24 * 60 * 60
        cur.execute("SELECT DISTINCT taskID FROM Fights WHERE value = 1 AND endTime >= ?", [startingDate])
        tasks = [x[0] for x in cur.fetchall()]
        taskCounts = {}
        tasksFound = False
        for tid in tasks:
            cur.execute("SELECT COUNT(*) FROM Fights WHERE taskID = ? AND value = 1 AND endTime >= ?", [tid, startingDate])
            taskCounts[tid] = cur.fetchall()[0][0]
            if (isComplete(tid) and completed) or (not isComplete(tid) and not completed): tasksFound = True
        if tasksFound:
            top = Toplevel()
            for tid in sorted(tasks, key=lambda x:taskCounts[x], reverse=True):
                if ( (isComplete(tid) and completed) or (not isComplete(tid) and not completed) ) and taskCounts[tid] > 0:
                    taskFrame= Frame(top)
                    taskLabel = Label(taskFrame, text=getTaskName(tid))
                    countLabel = Label(taskFrame, text=('x'+str(taskCounts[tid])))
                    if completed:
                        dateLabel = Label(taskFrame, text = getDateString(getCompletionExpirationDate(tid)), fg='dark red')
                    else:
                        dateLabel = Label(taskFrame, text = "")                   
                    cur.execute("SELECT startTime, endTime FROM Fights WHERE taskID = ? AND value = 1 ORDER BY endTime DESC LIMIT 1", [tid])                       
                    lastFight = cur.fetchall()[0]
                    taskLabel.bind('<Double-Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                    countLabel.bind('<Double-Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                    dateLabel.bind('<Double-Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                    taskLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], -1))
                    countLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], -1))
                    dateLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], -1))
                    taskLabel.pack(side=LEFT)
                    countLabel.pack(side=LEFT)
                    dateLabel.pack(side=LEFT)
                    taskFrame.pack()   
    return showTasks_inner

def completeTask(tid, inf=False):
    def completeTask_inner(_):
        if not inf:
            playAudio(soundFiles[4])
            try:
                expiration = int(entryText.get()) * 60 * 60
                entryText.set("")
            except:
                expiration = defaultCompletionExpiration * 60 * 60
        else:
            expiration = float("inf")
            playAudio(soundFiles[5]) 
    
        cur.execute("UPDATE Tasks SET complete=? WHERE id=?", [time.time()+expiration, tid])
        con.commit()
    return completeTask_inner

def isComplete(tid):
    cur.execute("SELECT complete FROM Tasks WHERE id=?", [tid])
    if cur.fetchall()[0][0] > time.time():
        return True
    else:
        return False
    
def getCompletionExpirationDate(tid):
    cur.execute("SELECT complete FROM Tasks WHERE id=?", [tid])
    return cur.fetchall()[0][0]
        
        
def getRealDuration(dur):
    if dur == float("inf"):
        cur.execute("SELECT MIN(endTime) FROM Fights")
        firstTime = cur.fetchall()[0][0];
        return int((time.time() - firstTime) / 24 / 60 / 60)
    else:
        return dur

    
def playAudio(filename):
    if filename.endswith('wav'):
        winsound.PlaySound(filename, winsound.SND_ASYNC | winsound.SND_FILENAME)
    else:
        os.startfile(filename)
                
            
def num2str(dur):
    if dur == float("inf"):
        return u'\u221e'
    elif dur == 0.25:
        return u'\u00BC'
    else:
        return dur

def reloadMain():
    # get tasks
    for child in root.winfo_children():
        child.destroy()
        
    startingDate = time.time() -  duration[pastshown] * 24 * 60 * 60
    startingDate2 = time.time() -  2 * duration[pastshown] * 24 * 60 * 60
    global taskPos, activeTasks, nextMainReload
    taskPos = 0    
         
    cur.execute("SELECT taskId, startTime, endTime FROM Fights WHERE value = 0")
    rows = cur.fetchall()
    activeTasks = [x[0] for x in filter(lambda x: x[2] > time.time(), rows)]
    rows.sort(key = lambda x: x[2], reverse = False)
    timeLeftList = []
    for tid, timestamp, deadline in rows:
        taskFrame= Frame(root)
        taskLabel = Label(taskFrame, text=getTaskName(tid))
        taskLabel.pack(side=LEFT)
        timeLeft = deadline - time.time()
        if timeLeft > 0:
            timeLeftList.append(timeLeft)
            fightProgress = IntVar()
            fightProgress.set(time.time()-timestamp)
            timeLabel = ttk.Progressbar(taskFrame, orient="horizontal", length=50, mode="determinate", variable=fightProgress, maximum=deadline-timestamp+1)
            timeLabel.start(1000)            
            timeLabel.pack(side=LEFT)
            taskLabel.bind('<Double-Button-1>', rescheduleFight(tid, timestamp, deadline))
            timeLabel.bind('<Double-Button-1>', rescheduleFight(tid, timestamp, deadline))
        else:
            playAudio(soundFiles[1])
            flightButton = Button(taskFrame, text=u"\u2717", fg="white", bg="gray60")
            flightButton.configure(command=resolveFight(tid, timestamp, deadline, -1))
            flightButton.pack(side=RIGHT)
            fightButton = Button(taskFrame, text=u"\u2714", fg="white", bg="red")
            fightButton.configure(command=resolveFight(tid, timestamp, deadline, 1))
            fightButton.pack(side=RIGHT)
        taskFrame.pack()   
    
    # schedule reload for when first deadline of an active task is reached     
    if len(timeLeftList) > 0:
        if nextMainReload is not None: root.after_cancel(nextMainReload)
        nextMainReload = root.after(int(min(timeLeftList)*1000), reloadMain)
    
    entryFrame = Frame(root)
    e = Entry(entryFrame, textvariable=entryText)
    e.pack()
    e.focus_set()
    e.bind('<Return>', addNewTask) 
    e.bind('<Down>', lambda _: proposeTask(skipChange=1))
    e.bind('<Up>', lambda _: proposeTask(skipChange=-1))
    e.bind('<Double-Button-1>', showTasks())
    e.bind('<Double-Button-3>', showTasks(True))
    quickInfo = Label(entryFrame, textvariable=quickInfoText)
    quickInfo.pack(side=RIGHT)
    entryFrame.pack()

    cur.execute("SELECT taskID FROM Fights WHERE value = 1 ORDER BY endTime DESC LIMIT 1")
    lastTaskID = cur.fetchall()[0][0]
    cur.execute("SELECT MIN(endTime) FROM Fights WHERE value = 1 AND taskID = ?", [lastTaskID])
    firstTime = cur.fetchall()[0][0]
    cur.execute("SELECT COUNT(*) FROM Fights WHERE taskID = ? AND value = 1 AND endTime >= ? AND endTime <= ?", [lastTaskID, startingDate2, startingDate])
    lastFightTotal2 = cur.fetchall()[0][0]
    cur.execute("SELECT COUNT(*) FROM Fights WHERE taskID = ? AND value = 1 AND endTime >= ? AND endTime <= ?", [lastTaskID, startingDate, time.time()])
    lastFightTotal1 = cur.fetchall()[0][0]
    if lastFightTotal1 > lastFightTotal2:
        arrow = u'\u279a'
    elif lastFightTotal1 == lastFightTotal2:
        arrow = u'\u2192'
    else:
        arrow = u'\u2798'    
    sumFightText = getTaskName(lastTaskID)+"\n" + (str(lastFightTotal2)+arrow if firstTime<startingDate else "") + str(lastFightTotal1)
    sumFightLabel = Label(root, text=sumFightText)
    if firstTime<startingDate: 
        sumFightLabel.bind('<Double-Button-1>', showHistory(lastTaskID))
    sumFightLabel.bind('<Double-Button-3>', completeTask(lastTaskID))
    sumFightLabel.bind('<Triple-Button-3>', completeTask(lastTaskID, True))
    sumFightLabel.pack(side=LEFT)

    pastshownButton = Button(root, text=num2str(duration[pastshown]), command=changePastShown(1))
    pastshownButton.bind('<Button-3>', changePastShown(-1))    
    pastshownButton.pack(side=RIGHT)
    
        
# load audio
soundFiles = []
for line in open(soundPlaylist):
    soundFiles.append(line.strip()) 

# set up database if it does not already exist
con = lite.connect(taskDB)
with con:    
    cur = con.cursor()
    try:
        cur.execute("CREATE TABLE Tasks(id INTEGER PRIMARY KEY, name TEXT UNIQUE, complete INTEGER);")
        cur.execute("CREATE TABLE Fights(startTime INTEGER, endTime INTEGER, value INTEGER, taskId INTEGER, FOREIGN KEY(taskId) REFERENCES Tasks(id));")
        print 'Created new database.'
    except:
        print 'Found existing database.'

root = Tk()
entryText = StringVar()
quickInfoText = StringVar()
root.wm_title("Fight or Flight")
root.minsize(200, 100)
root.after(1, reloadMain)
root.after(1, periodicProposal)
root.mainloop()
configFile = open(configFileName, 'w')
config.write(configFile)
configFile.close()