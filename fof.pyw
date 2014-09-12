from Tkinter import *
import ttk
import sqlite3 as lite
import time
import ConfigParser
import os
import winsound
import datetime
import matplotlib.pyplot

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
    pastshown = 30
    proposalWaitTime = 60 * 60 * 1000
    quickInfoWaitTime = 5 * 1000
    defaultCompletionExpiration = 12
    historyGraphLength = 10
suggestionSkips = -1
clockStrings = {}
activeTasks = []
lastReloadTime = 0
lastSuggestion = None
quickInfoReset = None
nextMainReload = None
nextComplete = 0

def addNewTask(_):
    global pastshown
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
    elif len(line) > 0 and len(line.split()) == 1 and line.split()[0].isdigit():
        pastshown = int(line)
        config.set(config.sections()[0], "pastshown", pastshown)
        entryText.set("")   
        root.after(1, reloadMain)

def resolveFight(task_id, timeStart, timeEnd, value):
    def resolveFight_inner(_=None):
        global nextComplete
        cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [value, task_id, timeStart, timeEnd])
        con.commit()
        if value == 1:
            completeTask(task_id)
        elif value == -1:
            rescheduleFight(task_id, timeStart, timeEnd)(None)     
            playAudio(soundFiles[2])
        nextComplete = 0
        root.after(1, reloadMain)   
    return resolveFight_inner     

def prepareCompletion():
    def prepareCompletion_inner(_):
        global nextComplete
        if nextComplete == 0:
            try:
                nextComplete = float(entryText.get()) * 60 * 60
                entryText.set("")
            except:
                nextComplete = defaultCompletionExpiration * 60 * 60
        else:
            nextComplete = 0
        root.after(1, reloadMain)
    return prepareCompletion_inner
    

def completeTask(tid):
    if nextComplete > 0:
        if nextComplete == float('inf'):
            playAudio(soundFiles[5]) 
        else:
            playAudio(soundFiles[4])
        cur.execute("UPDATE Tasks SET complete=? WHERE id=?", [time.time()+nextComplete, tid])
        con.commit()
    else:
        playAudio(soundFiles[3])   


def periodicProposal():
    global suggestionSkips, proposalWaitTime, activeTasks
    suggestionSkips = -1
    if len(activeTasks) == 0:
        proposeTask(beepThreshold = pastshown)
    else:
        proposeTask()
    root.after(proposalWaitTime, periodicProposal)

             
def proposeTask(skipChange = 0, beepThreshold = 0):
    global suggestionSkips, activeTasks
    suggestionSkips += skipChange
    if suggestionSkips < 0: suggestionSkips = 0
    found = False
    days = 0
    skipsLeft = suggestionSkips
    window = 60*60
    while not found and days <= maxDays:
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
    if days > maxDays:
        suggestionSkips -= 1
    
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
        return u'\u221e'

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
            end = time.time() - period * pastshown * 24 * 60 * 60
            start = time.time() -  (period+1) * pastshown * 24 * 60 * 60
            cur.execute("SELECT COUNT(*) FROM Fights WHERE taskID = ? AND value = 1 AND endTime >= ? AND endTime <= ?", [tid, start, end])
            history.append(cur.fetchall()[0][0])
            period += 1
        matplotlib.pyplot.clf()
        matplotlib.pyplot.plot(history[::-1], 'ro-')
        matplotlib.pyplot.show()
    return showHistory_inner

def showTasks():
    def showTasks_inner(_):
        startingDate = time.time() -  pastshown * 24 * 60 * 60
        cur.execute("SELECT DISTINCT taskID FROM Fights WHERE value = 1 AND endTime >= ?", [startingDate])
        tasks = [x[0] for x in cur.fetchall()]
        taskCounts = {}
        for tid in tasks:
            cur.execute("SELECT COUNT(*) FROM Fights WHERE taskID = ? AND value = 1 AND endTime >= ?", [tid, startingDate])
            taskCounts[tid] = cur.fetchall()[0][0]
        if len(tasks) > 0:
            top = Toplevel()
            for tid in sorted(tasks, key=lambda x:taskCounts[x]*(1-isComplete(x)), reverse=True):
                completed = isComplete(tid)
                taskFrame= Frame(top)
                taskLabel = Label(taskFrame, text=getTaskName(tid), fg='dark red' if completed else 'black')
                countLabel = Label(taskFrame, text=('x'+str(taskCounts[tid])), fg='dark red' if completed else 'black')
                dateLabel = Label(taskFrame, text = getDateString(getCompletionExpirationDate(tid)) if completed else '', fg='dark red')               
                cur.execute("SELECT startTime, endTime FROM Fights WHERE taskID = ? AND value = 1 ORDER BY endTime DESC LIMIT 1", [tid])                       
                lastFight = cur.fetchall()[0]
                taskLabel.bind('<Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                countLabel.bind('<Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                dateLabel.bind('<Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                taskLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], -1))
                countLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], -1))
                dateLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], -1))
                taskLabel.pack(side=LEFT)
                countLabel.pack(side=LEFT)
                dateLabel.pack(side=LEFT)
                taskFrame.pack()   
    return showTasks_inner

def isComplete(tid):
    cur.execute("SELECT complete FROM Tasks WHERE id=?", [tid])
    if cur.fetchall()[0][0] > time.time():
        return True
    else:
        return False
    
def getCompletionExpirationDate(tid):
    cur.execute("SELECT complete FROM Tasks WHERE id=?", [tid])
    return cur.fetchall()[0][0]
          
def playAudio(filename):
    if filename.endswith('wav'):
        winsound.PlaySound(filename, winsound.SND_ASYNC | winsound.SND_FILENAME)
    else:
        os.startfile(filename)                
            
def reloadMain():
    # get tasks
    for child in root.winfo_children():
        child.destroy()
        
    startingDate = time.time() -  pastshown * 24 * 60 * 60
    startingDate2 = time.time() -  2 * pastshown * 24 * 60 * 60
    global taskPos, activeTasks, nextMainReload
    taskPos = 0    
         
    cur.execute("SELECT taskId, startTime, endTime FROM Fights WHERE value = 0")
    rows = cur.fetchall()
    activeTasks = [x[0] for x in filter(lambda x: x[2] > time.time(), rows)]
    rows.sort(key = lambda x: x[2], reverse = False)
    timeLeftList = []
    waitingForResolution = False
    for tid, timestamp, deadline in rows:
        taskFrame= Frame(root)
        timeLeft = deadline - time.time()
        if timeLeft > 0 or waitingForResolution:
            taskLabel = Label(taskFrame, text=getTaskName(tid))
            taskLabel.pack(side=LEFT)
            fightProgress = IntVar()
            fightProgress.set(min(time.time()-timestamp, deadline-timestamp+1))
            taskDuration = deadline-timestamp
            timeLabel = ttk.Progressbar(taskFrame, orient="horizontal", length=50, mode="determinate", variable=fightProgress, maximum=taskDuration)
            timeLabel.pack(side=LEFT)
            taskLabel.bind('<Button-1>', rescheduleFight(tid, timestamp, deadline))
            timeLabel.bind('<Button-1>', rescheduleFight(tid, timestamp, deadline))
            if timeLeft > 0:
                timeLabel.start(1000) 
                timeLeftList.append(timeLeft)    
        else:
            if timeLeft > -1: playAudio(soundFiles[1])
            waitingForResolution = True
            taskLabel = Label(taskFrame, text=getTaskName(tid), fg='dark red' if nextComplete > 0 else 'black')
            taskLabel.pack(side=LEFT)
            cur.execute("SELECT taskID FROM Fights WHERE value <> -1 ORDER BY endTime DESC LIMIT 1")
            cur.execute("SELECT COUNT(*) FROM Fights WHERE taskID = ? AND value = 1 AND endTime >= ? AND endTime <= ?", [tid, startingDate2, startingDate])
            lastFightTotal2 = cur.fetchall()[0][0]
            cur.execute("SELECT COUNT(*) FROM Fights WHERE taskID = ? AND value = 1 AND endTime >= ? AND endTime <= ?", [tid, startingDate, time.time()])
            lastFightTotal1 = cur.fetchall()[0][0]
            if lastFightTotal1 > lastFightTotal2:
                arrow = u'\u279a'
            elif lastFightTotal1 == lastFightTotal2:
                arrow = u'\u2192'
            else:
                arrow = u'\u2798'    
            sumFightText = str(lastFightTotal2) + arrow + str(lastFightTotal1)
            sumFightLabel = Label(taskFrame, text=sumFightText, fg='dark red' if nextComplete > 0 else 'black')
            taskLabel.bind('<Button-1>', showHistory(tid))
            taskLabel.bind('<Button-3>', prepareCompletion())
            sumFightLabel.bind('<Button-1>', showHistory(tid))
            sumFightLabel.bind('<Button-3>', prepareCompletion())
            sumFightLabel.pack(side=RIGHT)
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
    e.bind('<Button-3>', showTasks())
    quickInfo = Label(entryFrame, textvariable=quickInfoText)
    quickInfo.pack(side=RIGHT)
    entryFrame.pack()


    
        
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
    try:
        cur.execute("SELECT MIN(endTime) FROM Fights")
        maxDays = int((time.time()-cur.fetchall()[0][0])/60/60/24)
    except:
        maxDays = pastshown


root = Tk()
entryText = StringVar()
quickInfoText = StringVar()
root.wm_title("Fight or Flight")
root.minsize(200, 50)
root.after(1, reloadMain)
root.after(1, periodicProposal)
root.mainloop()
configFile = open(configFileName, 'w')
config.write(configFile)
configFile.close()