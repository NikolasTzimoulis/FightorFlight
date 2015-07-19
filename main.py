from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.dropdown import DropDown
from kivy.uix.popup import Popup
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
import sqlite3 as lite
import time
import ConfigParser
from functools import partial

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
except:
    print "Could not load config file. Reverting to default values."
    pastshown = 30 * 24 * 60 * 60
    proposalWaitTime = 60 * 60 * 1000
    quickInfoWaitTime = 5 * 1000
    defaultCompletionExpiration = 12 * 60 * 60
    
    
def getTaskName(tid):
    cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
    return cur.fetchall()[0][0]

def getTaskId(tname):
    cur.execute("SELECT id FROM Tasks WHERE name = ?", [tname])
    return cur.fetchall()[0][0]

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
    
def isRunning(tid):
    cur.execute("SELECT COUNT(*) FROM Fights WHERE taskId = ? AND value = 0 AND endTime > ?", [tid, time.time()])
    if cur.fetchall()[0][0] > 0: return True
    else: return False

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
    
    # sum running duration and completion time for tasks in this time period
    score = sum([x[1]-x[0]+x[2] for x in rows])
    # stretch time period duration so that edge tasks don't inflate the score
    try: actualStart = min ( start ,  min([x[0] for x in rows]) )
    except: actualStart = start
    try: actualEnd = max ( end,  max([x[1]+x[2] for x in rows]) )
    except: actualEnd = end 
    
    if score == (actualEnd-actualStart): return 1.0
    return score/(actualEnd-actualStart)

def getScoreText(score, plusone=False):
    return str((10 if plusone else 0) + 10*int(10*score))+"%"

def playAudio(filename):
    sound = SoundLoader.load(filename)
    if sound: sound.play()
    

class MainScreen(BoxLayout):
    
    nextReload = None

    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.clear_widgets()
        self.showCompletedTasks = False
        cur.execute("SELECT taskId, startTime, endTime FROM Fights WHERE value = 0")
        rows = cur.fetchall()
        rows.sort(key = lambda x: x[2], reverse = False)
        timeLeftList = []
        self.progressbars = []
        enableNewTask = True
        for tid, timestamp, deadline in rows:
            taskLayout = BoxLayout(orientation='horizontal')
            self.add_widget(taskLayout)
            timeLeft = deadline - time.time()
            if timeLeft > 0:
                taskLabel = Label(text=getTaskName(tid), text_size=(200, 100), valign = 'middle', halign='center')
                taskLayout.add_widget(taskLabel)
                taskProgress = ProgressBar(max=deadline-timestamp)
                self.progressbars.append(taskProgress)
                taskLayout.add_widget(taskProgress)
                taskProgress.value = (min(time.time()-timestamp, deadline-timestamp+1))
                taskLayout.bind(on_touch_up=self.addNewTaskPopup(tid, int((deadline-timestamp)/60)))
                if timeLeft > 0: 
                    timeLeftList.append(timeLeft)
            else:
                if timeLeft > -1: playAudio(soundFiles[1])    
                taskLabel = Label(text=getTaskName(tid), text_size=(200, 100), valign = 'middle', halign='center')
                taskLayout.add_widget(taskLabel)
                fightButton = Button(background_color=(1,0,0,1))
                fightButton.bind(on_press=self.getCompletionTime(tid, timestamp, deadline))
                taskLayout.add_widget(fightButton)
                flightButton = Button(background_color=(0.6,0.6,0.6,1))
                flightButton.bind(on_press=self.resolveFight(tid, timestamp, deadline, -1))
                taskLayout.add_widget(flightButton)
                enableNewTask = False
                break
        if enableNewTask:
            newTaskButton = Button(text='+', font_size=100, background_color=(0.2,0.7,1,1))
            newTaskButton.bind(on_press=self.addNewTaskPopup())
            self.add_widget(newTaskButton)
                        
        Clock.unschedule(self.incrementProgressBars)
        Clock.schedule_interval(self.incrementProgressBars, 1)
            # schedule reload for when first deadline of an active task is reached
        if len(timeLeftList) > 0:
            if MainScreen.nextReload is not None: Clock.unschedule(lambda td:self.__init__())
            MainScreen.nextReload = Clock.schedule_once(lambda td:self.__init__(), min(timeLeftList))
    
    def incrementProgressBars(self, dt): 
        for pb in self.progressbars:
            pb.value+=1
            
    def addNewTaskPopup(self, defaultTask = None, defaultDuration = 1):
        def addNewTaskPopup_inner(_,__=None):
            popupLayout = BoxLayout(orientation='horizontal')
            taskDropdownIncomplete = DropDown()
            taskDropdownComplete =  DropDown()
            popup = Popup(title='',
            content=popupLayout,
            size_hint=(None, None), size=(800, 200))
            cur.execute("SELECT DISTINCT taskID FROM Fights WHERE value > 0")
            tasks = [x[0] for x in cur.fetchall()]
            firstTask = defaultTask
            for tid in sorted(tasks, key=lambda x:getScore(x, time.time()-pastshown, time.time()), reverse=True):
                if isRunning(tid): continue
                score = getScore(tid, time.time()-pastshown, time.time())
                scoreColor = (1,1-score,1-score,1)
                #print getTaskName(tid), score
                btn = Button(text=getTaskName(tid), bold=score>=0.99, color = scoreColor, background_color = (0,0,0,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
                if not isComplete(tid):
                    if firstTask is None and not self.showCompletedTasks: firstTask = tid
                    curTaskDropDown = taskDropdownIncomplete
                else:
                    if firstTask is None and self.showCompletedTasks: firstTask = tid
                    curTaskDropDown = taskDropdownComplete
                btn.bind(on_release=lambda btn: curTaskDropDown.select(btn.text))
                curTaskDropDown.add_widget(btn)
            taskSelector = Button(text=getTaskName(firstTask), text_size=(200, 100), valign = 'middle', halign='center')
            if self.showCompletedTasks:
                taskSelector.bind(on_release=taskDropdownComplete.open)
            else:
                taskSelector.bind(on_release=taskDropdownIncomplete.open)
            taskDropdownIncomplete.bind(on_select=lambda instance, x: setattr(taskSelector, 'text', x))
            popupLayout.add_widget(taskSelector)
            durationInput = TextInput(text=str(defaultDuration), input_filter='int')
            durationInput.bind(on_triple_tap=self.changeTaskType(popup))
            popupLayout.add_widget(durationInput)
            addButton = Button(text='+', font_size=100, background_color=(0.2,0.7,1,1))
            popupLayout.add_widget(addButton)
            addButton.bind(on_press=self.addNewTask(taskSelector, durationInput, popup))
            popup.open()  
        return addNewTaskPopup_inner
    
    def changeTaskType(self, popup=None):
        def changeTaskType_inner(_=None):
            if self.showCompletedTasks: self.showCompletedTasks = False
            else: self.showCompletedTasks = True       
            playAudio(soundFiles[0]) 
            if popup is not None: popup.dismiss()
        return changeTaskType_inner
        
    def addNewTask(self, taskSelector, durationInput, popup=None):
        def addNewTask_inner(_=None):
            if popup is not None: popup.dismiss()
            tid = getTaskId(taskSelector.text)
            duration = 60*int(durationInput.text)
            cur.execute("UPDATE Fights SET value=-1 WHERE taskId=? AND value = 0 AND startTime <= ?;", [tid, time.time()])
            unComplete(tid)
            cur.execute("INSERT INTO Fights VALUES(?, ?, ?, ?)", [time.time(), time.time()+duration, 0, tid])
            con.commit() 
            Clock.schedule_once(lambda td:self.__init__())
        return addNewTask_inner
    
    def getCompletionTime(self, tid, timestamp, deadline, timeEnd=time.time()):
        def getCompletionTime_inner(_=None):
            popupLayout = BoxLayout(orientation='horizontal')
            completionTimeInput = TextInput(text=str(defaultCompletionExpiration/60/60), input_filter='int')
            popupLayout.add_widget(completionTimeInput)
            fightButton = Button(background_color=(1,0,0,1))
            popupLayout.add_widget(fightButton)
            popup = Popup(title='',
            content=popupLayout,
            size_hint=(None, None), size=(400, 200))
            fightButton.bind(on_press=self.resolveFight(tid, timestamp, deadline, 1, completionTimeInput, popup))
            popup.open()  
        return getCompletionTime_inner
            
    def resolveFight(self, task_id, timeStart, timeEnd, success, completionTimeInput=None, popup=None):
        def resolveFight_inner(_=None):
            global waitingForResolution
            if popup is not None: popup.dismiss()
            oldScore = getScore(task_id, time.time()-pastshown, time.time())
            if success >= 0:
                if success == 0: 
                    completionTime = 1
                    deadline = time.time()
                    cur.execute("UPDATE Fights SET endTime=? WHERE taskId=? AND startTime=? AND endTime =?;", [deadline, task_id, timeStart, timeEnd])
                else:
                    deadline = timeEnd
                completionTime = completionTime=60*60*int(completionTimeInput.text)
                cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [completionTime, task_id, timeStart, deadline])
                con.commit()     
            elif success == -1:
                cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [-1, task_id, timeStart, timeEnd])  
                playAudio(soundFiles[2])
            con.commit()
            self.makeScoreProgressPopup(task_id, oldScore)
            Clock.schedule_once(lambda td:self.__init__())
        return resolveFight_inner       
    
    def makeScoreProgressPopup(self, tid, oldScore):
            newScore = getScore(tid, time.time()-pastshown, time.time())
            #print oldScore, '->', newScore
            scoreLayout = BoxLayout(orientation='vertical')
            scoreLayout.add_widget(Label(text=getTaskName(tid), text_size=(250, 200), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100))
            progressLayout = BoxLayout(orientation='horizontal')
            prevScoreMilestone = Label(text=getScoreText(oldScore))
            prevScoreMilestone.color = (1,1-float(prevScoreMilestone.text[:-1])/100,1-float(prevScoreMilestone.text[:-1])/100,1)
            progressLayout.add_widget(prevScoreMilestone)
            scoreProgress = ProgressBar(max=0.1)
            progressLayout.add_widget(scoreProgress)
            nextScoreMilestone = Label(text=getScoreText(oldScore, True))
            nextScoreMilestone.color = (1,1-float(nextScoreMilestone.text[:-1])/100,1-float(nextScoreMilestone.text[:-1])/100,1)
            nextScoreMilestone.bold = nextScoreMilestone.text == '100%'
            progressLayout.add_widget(nextScoreMilestone)
            scoreLayout.add_widget(progressLayout)            
            scorePopup = Popup(title='',
            content=scoreLayout,
            size_hint=(None, None), size=(250, 200))
            scorePopup.open()  
            Clock.schedule_once(scorePopup.dismiss, 5)
            Clock.schedule_interval(self.incrementScoreProgress(scoreProgress, prevScoreMilestone, nextScoreMilestone, oldScore, newScore), 0.1)
            
    def incrementScoreProgress(self, scoreProgress, prevScoreMilestone, nextScoreMilestone, oldScore, newScore):              
        def incrementScoreProgress_inner(_=None):
            if getScoreText(newScore) == prevScoreMilestone.text and scoreProgress.value >= newScore % 0.1:
                Clock.unschedule(self.incrementScoreProgress)    
            else: 
                if getScoreText(newScore) == prevScoreMilestone.text and newScore % 0.1 - scoreProgress.value <= 0.02:
                    scoreProgress.value = newScore % 0.1
                else:
                    scoreProgress.value += 0.02
                if scoreProgress.value >= scoreProgress.max:
                    playAudio(soundFiles[3])
                    if not nextScoreMilestone.text == '100%':
                        scoreProgress.value = 0
                        prevScoreMilestone.text = str(10+int(prevScoreMilestone.text[:-1]))+'%'
                        prevScoreMilestone.color = (1,1-float(prevScoreMilestone.text[:-1])/100,1-float(prevScoreMilestone.text[:-1])/100,1)
                        nextScoreMilestone.text = str(10+int(nextScoreMilestone.text[:-1]))+'%'
                        nextScoreMilestone.color = (1,1-float(nextScoreMilestone.text[:-1])/100,1-float(nextScoreMilestone.text[:-1])/100,1)
                        nextScoreMilestone.bold = nextScoreMilestone.text == '100%'
        return incrementScoreProgress_inner   

class FoFApp(App):

    def build(self):
        return MainScreen()


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
        cur.execute("CREATE TABLE Stress(time INTEGER, value INTEGER)")
        print 'Created new database.'
    except:
        print 'Found existing database.'
    try:
        cur.execute("SELECT MIN(endTime) FROM Fights")
        maxDays = int((time.time()-cur.fetchall()[0][0])/60/60/24)
    except:
        maxDays = pastshown / 24 / 60 / 60

if __name__ == '__main__':
    FoFApp().run()