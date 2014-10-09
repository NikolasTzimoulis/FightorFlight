import matplotlib.pyplot
matplotlib.use('TkAgg')
from Tkinter import *
import ttk
import sqlite3 as lite
import time
import ConfigParser
import os
import winsound
import datetime

taskDB = "fof.db"
soundPlaylist = "sounds.m3u"
configFileName = "config.ini"
config = ConfigParser.ConfigParser()
try:
    config.read(configFileName)
    pastshown = config.getint(config.sections()[0], "pastshown") * 24 * 60 * 60
    proposalWaitTime = config.getint(config.sections()[0], "proposalwaittime") * 1000 * 60
    quickInfoWaitTime = config.getint(config.sections()[0], "quickinfowaittime") * 1000
    defaultCompletionExpiration = config.getint(config.sections()[0], "defaultcompletionexpiration") * 60 * 60
    historyGraphLength = config.getint(config.sections()[0], "historygraphlength")
except:
    print "Could not load config file. Reverting to default values."
    pastshown = 30 * 24 * 60 * 60
    proposalWaitTime = 60 * 60 * 1000
    quickInfoWaitTime = 5 * 1000
    defaultCompletionExpiration = 12 * 60 * 60
    historyGraphLength = 10
suggestionSkips = -1
clockStrings = {}
undecidedTasks = []
lastReloadTime = 0
waitingForResolution = False
lastSuggestion = None
quickInfoReset = None
nextMainReload = None

def addNewTask(_):
    global pastshown
    line = entryText.get()
    duration = getSeconds(line.split()[-1])
    if len(line) > 0 and line.split()[0].isalpha() and duration is not None:
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
        unComplete(tid)
        cur.execute("INSERT INTO Fights VALUES(?, ?, ?, ?)", [time.time(), time.time()+duration, 0, tid])
        con.commit() 
        entryText.set("")
        root.after(1, reloadMain)
    elif len(line) > 0 and len(line.split()) == 1 and duration is not None:
        pastshown = duration
        config.set(config.sections()[0], "pastshown", int(pastshown / 24 / 60 / 60))
        entryText.set("")   
        root.after(1, reloadMain)

def resolveFight(task_id, timeStart, timeEnd, success):
    def resolveFight_inner(_=None):
        global waitingForResolution
        if success:
            completionTime = getCompletionTime()
            cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [completionTime, task_id, timeStart, timeEnd])
            if completionTime == float('inf'):
                playAudio(soundFiles[5]) 
            elif completionTime > defaultCompletionExpiration:
                playAudio(soundFiles[4])
            else:
                playAudio(soundFiles[3])   
        elif not success:
            cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [-1, task_id, timeStart, timeEnd])
            rescheduleFight(task_id, timeStart, timeEnd)(None)     
            playAudio(soundFiles[2])
        con.commit()
        waitingForResolution = False
        root.after(1, reloadMain)
    return resolveFight_inner     

def getCompletionTime(peek=False):
    global quickInfoReset
    completionTime = getSeconds(entryText.get())
    if completionTime is not None and not peek: 
        entryText.set("")
    elif completionTime is None:
        completionTime = defaultCompletionExpiration
    if not peek:
        quickInfoText.set(getDateString(time.time()+completionTime))
        if quickInfoReset is not None: root.after_cancel(quickInfoReset)
        quickInfoReset = root.after(quickInfoWaitTime, lambda: quickInfoText.set(''))
    return completionTime

def periodicProposal():
    global suggestionSkips, proposalWaitTime
    suggestionSkips = -1
    proposeTask(beepThreshold = pastshown)
    root.after(proposalWaitTime, periodicProposal)

             
def proposeTask(skipChange = 0, beepThreshold = 0):
    global suggestionSkips, undecidedTasks
    if waitingForResolution: return
    suggestionSkips += skipChange
    if suggestionSkips < 0: suggestionSkips = 0
    found = False
    days = 0
    skipsLeft = suggestionSkips
    window = 60*60
    while not found and days <= maxDays:
        days += 1
        pastDate = time.time() - days * 24 * 60 * 60
        cur.execute("SELECT taskId, startTime, endTime FROM Fights WHERE value > 0 AND startTime < ? AND endTime > ? ORDER BY startTime ASC", [pastDate+window, pastDate-window])
        rows = cur.fetchall()
        for fight in rows:
            if fight[0] in undecidedTasks or isComplete(fight[0]):
                continue
            elif skipsLeft > 0:
                skipsLeft -= 1
                continue
            else:
                found = True
                rescheduleFight(fight[0], fight[1], fight[2])(None)
                if days * 24 * 60 * 60 <= beepThreshold:
                    playAudio(soundFiles[0])
                break
    if days > maxDays:
        suggestionSkips -= 1
    
def rescheduleFight(tid, timestamp, deadline, reload=False):
    def rescheduleFight_inner(_):
        global quickInfoReset
        entryText.set(generateEntryText(tid, timestamp,deadline))
        quickInfoText.set(getDateString(deadline))
        if quickInfoReset is not None: root.after_cancel(quickInfoReset)
        quickInfoReset = root.after(quickInfoWaitTime, lambda: quickInfoText.set(''))    
        if reload: root.after(1, reloadMain)    
    return rescheduleFight_inner

def showHistory(tid, plusone=False):
    def showHistory_inner(_):
        end = time.time()
        period = 0
        history = []        
        improved = None
        for _ in range(historyGraphLength):
            end = time.time() - period * pastshown 
            start = time.time() -  (period+1) * pastshown 
            if plusone and improved is None: improved = getScore(tid, start, end, True)
            history.append( getScore(tid, start, end) )            
            period += 1
        matplotlib.pyplot.clf()
        if plusone:
            matplotlib.pyplot.plot(history[::-1], 'ko-')
            history[0] = improved
        matplotlib.pyplot.plot(history[::-1], 'ro-')
        matplotlib.pyplot.show()
    return showHistory_inner

def showTasks():
    def showTasks_inner(_):
        if waitingForResolution: return
        startingDate2 = time.time() -  2 * pastshown
        cur.execute("SELECT DISTINCT taskID FROM Fights WHERE value > 0 AND endTime >= ?", [startingDate2])
        tasks = [x[0] for x in cur.fetchall()]
        if len(tasks) > 0:
            top = Toplevel()
            for tid in sorted(tasks, key=lambda x:getCompletionExpirationDate(x)):
                completed = isComplete(tid)
                taskFrame= Frame(top)
                taskLabel = Label(taskFrame, text=getTaskName(tid), fg='dark red' if completed else 'black')
                countLabel = Label(taskFrame, text=getArrowString(tid), fg='dark red' if completed else 'black')
                dateLabel = Label(taskFrame, text = getDateString(getCompletionExpirationDate(tid)) if completed else '', fg='dark red')               
                cur.execute("SELECT startTime, endTime FROM Fights WHERE taskID = ? AND value > 0 ORDER BY endTime DESC LIMIT 1", [tid])                       
                lastFight = cur.fetchall()[0]
                taskLabel.bind('<Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                #taskLabel.bind('<Button-3>', showHistory(tid))
                countLabel.bind('<Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                dateLabel.bind('<Button-1>', rescheduleFight(tid, lastFight[0], lastFight[1], True))
                taskLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], False))
                countLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], False))
                dateLabel.bind('<Triple-Button-2>', resolveFight(tid, lastFight[0], lastFight[1], False))
                taskLabel.pack(side=LEFT)
                countLabel.pack(side=LEFT)
                dateLabel.pack(side=LEFT)
                taskFrame.pack()   
    return showTasks_inner

def getTaskName(tid):
    cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
    return cur.fetchall()[0][0]

def isComplete(tid):
    if getCompletionExpirationDate(tid) > time.time():
        return True
    else:
        return False
    
def getCompletionExpirationDate(tid):
    cur.execute("SELECT value, endTime FROM Fights WHERE taskId = ? AND value > 0 ORDER BY endTime DESC LIMIT 1", [tid])
    try:
        result = cur.fetchall()[0]
        return result[0]+result[1]
    except:
        return time.time() 

def unComplete(tid):
    if isComplete(tid):
        cur.execute("SELECT endTime FROM Fights WHERE taskId = ? ORDER BY endTime DESC LIMIT 1", [tid])        
        deadline = cur.fetchall()[0][0]
        cur.execute("UPDATE Fights SET value = ? WHERE taskId = ? AND endTime =  ?", [time.time() - deadline, tid, deadline])
        
def getScore(tid, start, end, plusone = False):   
    if not plusone:
        cur.execute("SELECT startTime, endTime, value FROM Fights WHERE taskID = ? AND value > 0 AND endTime+value >= ? AND startTime <= ?", [tid, start, end])
    else:
        cur.execute("SELECT startTime, endTime, value FROM Fights WHERE taskID = ? AND value >= 0 AND endTime+value >= ? AND startTime <= ?", [tid, start, end])
    rows = cur.fetchall()
    
    if plusone: # add expected completion time for the pledge that is still undecided
        rows = map(lambda x: [x[0], x[1], getCompletionTime(True) if x[2]==0 else x[2]], rows)
    # sum running duration and completion time for tasks in this time period
    score = sum([x[1]-x[0]+x[2] for x in rows])
    # stretch time period duration so that edge tasks don't inflate the score
    try: actualStart = min ( start ,  min([x[0] for x in rows]) )
    except: actualStart = start
    try: actualEnd = max ( end,  max([x[1]+x[2] for x in rows]) )
    except: actualEnd = end 
    
    if score == (actualEnd-actualStart): return 1.0
    return score/(actualEnd-actualStart)
    
def getArrowString(tid, plusone = False):
    startingDate = time.time() -  pastshown 
    startingDate2 = time.time() -  2 * pastshown 
    lastFightTotal2 = getScore(tid, startingDate2, startingDate)
    lastFightTotal1 = getScore(tid, startingDate, time.time(), plusone)
    if lastFightTotal1 > lastFightTotal2:
        arrow = u'\u279a'
    elif lastFightTotal1 == lastFightTotal2:
        arrow = u'\u2192'
    else:
        arrow = u'\u2798'    
    return str(round(lastFightTotal2,2)) + arrow + str(round(lastFightTotal1,2)) + ('?' if plusone else '')

def getSeconds(text):
    timeList = text.split(':')
    seconds = None
    try: seconds = float(timeList[-1]) * 60 
    except: return None
    if len(timeList) > 1:
        try: seconds += float(timeList[-2]) * 60 *60
        except: return None
    if len(timeList) > 2:
        try: seconds += float(timeList[-3]) * 24 * 60 *60
        except: return None
    return seconds
        
def generateEntryText(tid, timestamp, deadline):
    seconds = deadline - timestamp
    days, remainder = divmod(seconds, 24*60*60)
    hours, remainder = divmod(remainder, 60*60)
    minutes, seconds = divmod(remainder, 60)
    timeString = str(int(days))+':' if days > 0 else ''
    timeString += ('0' if days > 0 and hours < 10 else '') + str(int(hours))+':' if days > 0 or hours > 0 else ''
    timeString += ('0' if hours > 0 and minutes < 10 else '') + str(int(minutes))
    if tid is not None:
        return getTaskName(tid)+" "+  timeString
    else:
        return timeString

def getDateString(deadline):
    try:
        return datetime.datetime.fromtimestamp(deadline).strftime('%Y-%m-%d, %H:%M')
    except:
        return u'\u221e'
          
def playAudio(filename):
    if filename.endswith('wav'):
        winsound.PlaySound(filename, winsound.SND_ASYNC | winsound.SND_FILENAME)
    else:
        os.startfile(filename)                
            
def reloadMain():
    # get tasks
    for child in root.winfo_children():
        child.destroy()
        
    global taskPos, undecidedTasks, nextMainReload, waitingForResolution
    taskPos = 0    
         
    cur.execute("SELECT taskId, startTime, endTime FROM Fights WHERE value = 0")
    rows = cur.fetchall()
    undecidedTasks = map(lambda x: x[0], rows)
    rows.sort(key = lambda x: x[2], reverse = False)
    timeLeftList = []
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
            taskLabel = Label(taskFrame, text=getTaskName(tid), fg='black')
            taskLabel.pack(side=LEFT)
            sumFightLabel = Label(taskFrame, text=getArrowString(tid, plusone=True), fg='black')
            taskLabel.bind('<Button-1>', showHistory(tid, True))
            sumFightLabel.bind('<Button-1>', showHistory(tid, True))
            sumFightLabel.pack(side=LEFT)
            flightButton = Button(taskFrame, text=u"\u2717", fg="white", bg="gray60")
            flightButton.configure(command=resolveFight(tid, timestamp, deadline, False))
            flightButton.pack(side=RIGHT)
            fightButton = Button(taskFrame, text=u"\u2714", fg="white", bg="red")
            fightButton.configure(command=resolveFight(tid, timestamp, deadline, True))
            fightButton.pack(side=RIGHT)
            entryText.set(generateEntryText(None, 0, defaultCompletionExpiration))
            
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
        cur.execute("CREATE TABLE Tasks(id INTEGER PRIMARY KEY, name TEXT UNIQUE);")
        cur.execute("CREATE TABLE Fights(startTime INTEGER, endTime INTEGER, value INTEGER, taskId INTEGER, FOREIGN KEY(taskId) REFERENCES Tasks(id));")
        print 'Created new database.'
    except:
        print 'Found existing database.'
    try:
        cur.execute("SELECT MIN(endTime) FROM Fights")
        maxDays = int((time.time()-cur.fetchall()[0][0])/60/60/24)
    except:
        maxDays = pastshown / 24 / 60 / 60

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