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
    if tid is None: return ''
    cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
    return cur.fetchall()[0][0]

def getTaskId(tname):
    try:
        cur.execute("SELECT id FROM Tasks WHERE name = ?", [tname])
    except:
        cur.execute("SELECT id FROM Tasks WHERE name = ?", [tname.decode('utf-8')])        
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
        cur.execute("SELECT endTime FROM Fights WHERE value > 0 AND taskId = ? ORDER BY endTime DESC LIMIT 1", [tid])        
        deadline = cur.fetchall()[0][0]
        cur.execute("UPDATE Fights SET value = ? WHERE taskId = ? AND endTime =  ?", [time.time() - deadline, tid, deadline])
        con.commit()
        
def getScore(tid, start, end, plusone = False): # do NOT a default values for start and end!
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
                #taskLayout.bind(on_touch_up=self.addNewTaskPopup(tid, int((deadline-timestamp)/60)))
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
            newTaskButton = Button(text='+', font_size='100sp', background_color=(0.2,0.7,1,1))
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
            
    def addNewTaskPopup(self, defaultTask = None, defaultDuration = None):
        def addNewTaskPopup_inner(_,__=None):
            start = time.time()-pastshown
            end = time.time()
            popupLayout = BoxLayout(orientation='horizontal')
            tasksDropdown = DropDown()
            moreTaskDropdown =  DropDown()
            popup = Popup(title='',
            content=popupLayout,
            size_hint=(None, None), size=(800, 200))
            cur.execute("SELECT DISTINCT taskID FROM Fights WHERE value > 0")
            tasks = [x[0] for x in cur.fetchall()]
            firstTask = defaultTask
            for tid in sorted(tasks, key=lambda x:getScore(x, start, end), reverse=True):
                score = getScore(tid, start, end)
                scoreColor = (1,1-score,1-score,1)
                #print getTaskName(tid), score
                btn = Button(text=getTaskName(tid), bold=score>=0.99, color = scoreColor, background_color = (0.6,0.6,0.6,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
                if not isComplete(tid) and not isRunning(tid) and score > 0:
                    if firstTask is None: firstTask = tid
                    tasksDropdown.add_widget(btn) 
                    btn.bind(on_release=lambda btn: tasksDropdown.select(btn.text)) 
                else:
                    btn.bind(on_release=lambda btn: moreTaskDropdown.select(btn.text))
                    moreTaskDropdown.add_widget(btn)                
            moreTasksButton = Button(text='...', font_size='40sp', bold=True, background_color = (0.6,0.6,0.6,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            writeTaskButton = Button(text='+', font_size='40sp', bold=True, color=(0.2,0.7,1,1), background_color = (0.6,0.6,0.6,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            tasksDropdown.add_widget(moreTasksButton)
            moreTaskDropdown.add_widget(writeTaskButton)
            taskSelector = Button(text=getTaskName(firstTask), text_size=(200, 100), valign = 'middle', halign='center')
            taskSelector.bind(on_release=tasksDropdown.open)
            tasksDropdown.bind(on_select=lambda instance, x: setattr(taskSelector, 'text', x))
            moreTaskDropdown.bind(on_select=lambda instance, x: setattr(taskSelector, 'text', x))
            moreTasksButton.bind(on_release=self.showMoreTasks(moreTaskDropdown, tasksDropdown, taskSelector))
            writeTaskInput = TextInput(text='')
            writeTaskPopup = Popup(title='',
            content=writeTaskInput,
            size_hint=(None, None), size=(400, 200))
            writeTaskButton.bind(on_release=writeTaskPopup.open)
            writeTaskPopup.bind(on_dismiss=lambda _: setattr(taskSelector, 'text', writeTaskInput.text))
            popupLayout.add_widget(taskSelector)
            writeDurationButton = Button(text='+', font_size='40sp', bold=True, background_color = (0.6,0.6,0.6,1), color=(0.2,0.7,1,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            self.durationSelector = Button(text_size=(200, 100), valign = 'middle', halign='center')
            self.makeDurationDropdown(firstTask)
            if defaultDuration is not None: self.durationSelector.text = str(defaultDuration)
            self.durationDropdown.add_widget(writeDurationButton)
            self.durationSelector.bind(on_release=self.durationDropdown.open)
            self.durationDropdown.bind(on_select=lambda instance, x: setattr(self.durationSelector, 'text', x))
            writeDurationInput = TextInput(text=str(1), input_filter='int')
            writeDurationPopup = Popup(title='',
            content=writeDurationInput,
            size_hint=(None, None), size=(400, 200))
            writeDurationButton.bind(on_release=writeDurationPopup.open)
            writeDurationPopup.bind(on_dismiss=lambda _: setattr(self.durationSelector, 'text', writeDurationInput.text))
            popupLayout.add_widget(self.durationSelector)
            tasksDropdown.bind(on_select=lambda instance, changedTaskName:self.remakeDurationDropdown(changedTaskName, writeDurationButton))
            moreTaskDropdown.bind(on_select=lambda instance, changedTaskName:self.remakeDurationDropdown(changedTaskName, writeDurationButton))
            addButton = Button(text='+', font_size='70sp', background_color=(0.2,0.7,1,1))
            popupLayout.add_widget(addButton)
            addButton.bind(on_press=self.addNewTask(taskSelector, self.durationSelector, popup))
            popup.open()  
        return addNewTaskPopup_inner
    
    def showMoreTasks(self, newDropdown, oldDropdown, parent):
        def showshowMoreTasks_inner(_=None):
            newDropdown.open(parent)
            oldDropdown.dismiss()
        return showshowMoreTasks_inner
    
    def makeDurationDropdown(self, tid):
        cur.execute("SELECT endTime, startTime FROM Fights WHERE taskID = ? AND value > 0 ORDER BY endTime DESC", [tid])
        res = cur.fetchall()
        durations = [str(int((x[0]-x[1])/60)) for x in res]
        seen = set()
        durations = [ x for x in durations if not (x in seen or seen.add(x))]
        self.durationDropdown = DropDown()
        firstDuration = None
        for d in durations[:10]:
            if firstDuration is None: firstDuration = d
            btn = Button(text=d, text_size=(200, 100), background_color = (0.6,0.6,0.6,1), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            btn.bind(on_release=lambda btn: self.durationDropdown.select(btn.text))
            self.durationDropdown.add_widget(btn)
        if firstDuration is None: firstDuration = str(1)
        self.durationSelector.text = firstDuration
    
    def remakeDurationDropdown(self, tname, writeDurationButton):
        try:
            tid = getTaskId(tname)
        except:
            tid = None
        self.durationDropdown.clear_widgets()
        self.makeDurationDropdown(tid)
        self.durationDropdown.add_widget(writeDurationButton)
        self.durationDropdown.bind(on_select=lambda instance, x: setattr(self.durationSelector, 'text', x))
        self.durationSelector.bind(on_release=self.durationDropdown.open)
            
        
    def addNewTask(self, taskSelector, durationSelector, popup=None):
        def addNewTask_inner(_=None):
            if not taskSelector.text == '' and not durationSelector.text == '':
                if popup is not None: 
                    popup.dismiss()
                try:
                    tid = getTaskId(taskSelector.text)
                except:     
                    try:               
                        cur.execute("INSERT INTO Tasks(name) VALUES(?)", [taskSelector.text.strip()])
                    except:
                        cur.execute("INSERT INTO Tasks(name) VALUES(?)", [taskSelector.text.strip().decode('utf-8')])
                    con.commit()
                    tid = getTaskId(taskSelector.text)
                duration = 60*int(durationSelector.text)
                cur.execute("UPDATE Fights SET value=-1 WHERE taskId=? AND value = 0 AND startTime <= ?;", [tid, time.time()])
                unComplete(tid)
                cur.execute("INSERT INTO Fights VALUES(?, ?, ?, ?)", [time.time(), time.time()+duration, 0, tid])
                con.commit() 
                Clock.schedule_once(lambda td:self.__init__())
        return addNewTask_inner
    
    def getCompletionTime(self, tid, timestamp, deadline, timeEnd=time.time()):
        def getCompletionTime_inner(_=None):
            popupLayout = BoxLayout(orientation='horizontal')
            writeCompletionTimeInput = TextInput(text=str(defaultCompletionExpiration/60/60), input_filter='int')
            completionTimeDropdown = DropDown()
            completionTimeSelector = Button(text_size=(200, 100), valign = 'middle', halign='center')
            writecompletionTimeButton = Button(text='+', font_size='40sp', bold=True, color=(0.2,0.7,1,1), background_color = (0.6,0.6,0.6,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            cur.execute("SELECT value FROM Fights WHERE taskID = ? AND value > 0 ORDER BY endTime DESC", [tid])
            res = cur.fetchall()
            values= [str(int(x[0]/60/60)) for x in res]
            seen = set()
            values = [ x for x in values if not (x in seen or seen.add(x))]
            firstValue = None
            for v in values[:10]:
                if firstValue is None: firstValue = v
                btn = Button(text=v, background_color = (0.6,0.6,0.6,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
                btn.bind(on_release=lambda btn: completionTimeDropdown.select(btn.text))
                completionTimeDropdown.add_widget(btn)
            if firstValue is None: firstValue = str(defaultCompletionExpiration/60/60)
            completionTimeDropdown.add_widget(writecompletionTimeButton)
            completionTimeSelector.text = firstValue
            completionTimeDropdown.bind(on_select=lambda instance, x: setattr(completionTimeSelector, 'text', x))
            completionTimeSelector.bind(on_release=completionTimeDropdown.open)
            writeCompletionTimePopup = Popup(title='',
            content=writeCompletionTimeInput,
            size_hint=(None, None), size=(400, 200))
            writecompletionTimeButton.bind(on_release=writeCompletionTimePopup.open)
            writeCompletionTimePopup.bind(on_dismiss=lambda _: setattr(completionTimeSelector, 'text', writeCompletionTimeInput.text))            
            popupLayout.add_widget(completionTimeSelector)
            fightButton = Button(background_color=(1,0,0,1))
            popupLayout.add_widget(fightButton)
            popup = Popup(title='',
            content=popupLayout,
            size_hint=(None, None), size=(400, 200))
            fightButton.bind(on_press=self.resolveFight(tid, timestamp, deadline, 1, completionTimeSelector, popup))
            popup.open()  
        return getCompletionTime_inner
            
    def resolveFight(self, task_id, timeStart, timeEnd, success, completionTimeSelector=None, popup=None):
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
                try:
                    completionTime = 60*60*int(completionTimeSelector.text)+1
                except:
                    completionTime = 1
                cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [completionTime, task_id, timeStart, deadline])
                con.commit()
                self.makeScoreProgressPopup(task_id, oldScore)     
            elif success == -1:
                cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [-1, task_id, timeStart, timeEnd])  
                playAudio(soundFiles[2])
                Clock.schedule_once(self.addNewTaskPopup(task_id, int((timeEnd-timeStart)/60)),1)
            con.commit()
            Clock.schedule_once(lambda td:self.__init__())
        return resolveFight_inner       
    
    def makeScoreProgressPopup(self, tid, oldScore):
            newScore = getScore(tid, time.time()-pastshown, time.time())
            #print oldScore, '->', newScore
            scoreLayout = BoxLayout(orientation='vertical')
            scoreLayout.add_widget(Label(text=getTaskName(tid), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100))
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
            size_hint=(None, None), size=(400, 300))
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
                    if nextScoreMilestone.text == '100%':
                        playAudio(soundFiles[5])
                    elif nextScoreMilestone.text == '90%':
                        playAudio(soundFiles[4])
                    else:
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