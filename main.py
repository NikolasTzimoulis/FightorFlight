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
import datetime

__version__ = '1.0'
taskDB = "fof.db"
#taskDB = "/mnt/sdcard/kivy/fof/fof.db"
soundPlaylist = "sounds.m3u"
configFileName = "config.ini"
languagefile = "localisation.ini"
config = ConfigParser.ConfigParser()
try:
    config.read(configFileName)
    pastshown = config.getint(config.sections()[0], "pastshown") * 24 * 60 * 60
    proposalWaitTime = config.getint(config.sections()[0], "proposalwaittime") * 1000 * 60
    quickInfoWaitTime = config.getint(config.sections()[0], "quickinfowaittime") * 1000
    defaultCompletionExpiration = config.getint(config.sections()[0], "defaultcompletionexpiration") * 60 * 60
    language = config.get(config.sections()[0], "language")
except:
    print "Could not load config file. Reverting to default values."
    pastshown = 30 * 24 * 60 * 60
    proposalWaitTime = 60 * 60 * 1000
    quickInfoWaitTime = 5 * 1000
    defaultCompletionExpiration = 12 * 60 * 60
    language = "English"
    
localisation = ConfigParser.ConfigParser()
localisation.read(languagefile)
    
    
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
    return timeString

def durationToInt(text):
    negative = False
    if text.startswith("-"):
        negative = True
        text = text[1:]
    timeList = text.split(':')
    seconds = None
    try: seconds = float(timeList[-1]) * 60 
    except: return 0
    if len(timeList) > 1:
        try: seconds += float(timeList[-2]) * 60 *60
        except: return 0
    if len(timeList) > 2:
        try: seconds += float(timeList[-3]) * 24 * 60 *60
        except: return 0
    return seconds * (-1 if negative else 1) 

def durationInputFilter(text, isUndo):
    if text.isdigit() or text == ':': 
        return text
    else:
        return ''         

def getDateString(timestamp):
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d, %H:%M')
    except:
        return u'???'

def playAudio(filename):
    sound = SoundLoader.load(filename)
    if sound: sound.play()
    
class MainScreen(BoxLayout):
    
    nextReload = None
    cooldownDict = {}
    popups = 0

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
            taskLabel = Label(text=getTaskName(tid), text_size=(200, 100), valign = 'middle', halign='center')
            taskLayout.add_widget(taskLabel)
            taskProgress = ProgressBar(max=deadline-timestamp)
            self.progressbars.append(taskProgress)
            taskLayout.add_widget(taskProgress)
            taskProgress.value = (min(time.time()-timestamp, deadline-timestamp+1))
            if timeLeft > 0: 
                timeLeftList.append(timeLeft)
            else:
                if timeLeft > -1: playAudio(soundFiles[1]) 
                #taskLabel.bind(on_touch_up=self.taskPopup(tid,  timestamp, deadline))
                taskProgress.max = taskProgress.value = 1                
                #taskProgress.bind(on_touch_up=self.taskPopup(tid,  timestamp, deadline))
                if MainScreen.popups <= 0:
                    Clock.schedule_once(self.taskPopup(tid,  timestamp, deadline))
                else:
                    timeLeftList.append(1)  
                enableNewTask = False
                break
        if enableNewTask:
            newTaskButton = Button(text=localisation.get(language, "newtask"), font_size='30sp', background_color=(0.2,0.7,1,1))
            newTaskButton.bind(on_press=self.taskPopup())
            self.add_widget(newTaskButton)
                        
        Clock.unschedule(self.incrementProgressBars)
        Clock.schedule_interval(self.incrementProgressBars, 1)
        # schedule reload for when first deadline of an active task is reached 
        if len(timeLeftList) > 0:
            self.rescheduleMainWindowReload(min(timeLeftList))
        if not rows and enableNewTask:
            if MainScreen.popups <= 0:    
                Clock.schedule_once(self.taskPopup())
            else:
                self.rescheduleMainWindowReload(1)
            
            
    def rescheduleMainWindowReload(self, seconds):
        if MainScreen.nextReload is not None: Clock.unschedule(lambda td:self.__init__())
        MainScreen.nextReload = Clock.schedule_once(lambda td:self.__init__(), seconds)
    
    def incrementProgressBars(self, dt): 
        for pb in self.progressbars:
            pb.value+=1
            
    def decreasePopups(self, _):
        MainScreen.popups -= 1
            
    def taskPopup(self, finished_tid = None, finished_timestamp = None, finished_deadline = None):
        def taskPopup_inner(_,__=None):
            start = time.time()-pastshown
            end = time.time()
            Clock.unschedule(self.taskPopup)
            popupLayout = BoxLayout(orientation='vertical')
            popup = Popup(title=localisation.get(language,"newtask") if finished_tid is None else localisation.get(language,"confirm"),
            content=popupLayout,
            size_hint=(None, None), size=(800, 800))
            # task selection menu
            tasksDropdown = DropDown()
            moreTaskDropdown =  DropDown()
            cur.execute("SELECT DISTINCT taskID FROM Fights WHERE value > 0")
            tasks = [x[0] for x in cur.fetchall()]
            firstTask = finished_tid
            for tid in sorted(tasks, key=lambda x:getScore(x, start, end), reverse=True):
                score = getScore(tid, start, end)
                scoreColor = (1,1-score,1-score,1)
                #print getTaskName(tid), score
                btn = Button(text=getTaskName(tid), bold=score>=0.99, color = scoreColor, background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)                
                if not isComplete(tid) and not isRunning(tid) and score > 0:
                    if firstTask is None: firstTask = tid
                    tasksDropdown.add_widget(btn) 
                    btn.bind(on_release=lambda btn: tasksDropdown.select(btn.text)) 
                else:
                    btn.bind(on_release=lambda btn: moreTaskDropdown.select(btn.text))
                    moreTaskDropdown.add_widget(btn)                
            moreTasksButton = Button(text=localisation.get(language, "showmore"), bold=True, background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)
            writeTaskButton = Button(text=localisation.get(language, "createnew"), bold=True, color=(0.2,0.7,1,1), background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)
            tasksDropdown.add_widget(moreTasksButton)
            moreTaskDropdown.add_widget(writeTaskButton)
            taskSelector = Button(text=getTaskName(firstTask), text_size=(400, 100), valign = 'middle', halign='center')
            if finished_tid is None: taskSelector.bind(on_release=tasksDropdown.open)
            tasksDropdown.bind(on_select=lambda instance, x: setattr(taskSelector, 'text', x))
            moreTaskDropdown.bind(on_select=lambda instance, x: setattr(taskSelector, 'text', x))
            moreTasksButton.bind(on_release=self.showMoreTasks(moreTaskDropdown, tasksDropdown, taskSelector))
            writeTaskInput = TextInput(text='')
            writeTaskPopup = Popup(title=localisation.get(language, "createnew"),
            content=writeTaskInput,
            size_hint=(None, None), size=(400, 200))
            writeTaskButton.bind(on_release=writeTaskPopup.open)
            writeTaskPopup.bind(on_dismiss=lambda _: setattr(taskSelector, 'text', writeTaskInput.text))
            writeTaskPopup.bind(on_dismiss=moreTaskDropdown.dismiss)
            popupLayout.add_widget(taskSelector)
            # duration menu
            self.endLabel = Label(text_size=(400, 50), font_size='12sp', valign = 'bottom', halign='left')
            popupLayout.add_widget(self.endLabel)
            self.writeDurationButton = Button(text=localisation.get(language, "createnew"), bold=True, background_color = (0.6,0.6,0.6,1), color=(0.2,0.7,1,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            self.durationSelector = Button(text_size=(200, 100), valign = 'middle', halign='center')
            self.makeDurationDropdown(firstTask, finished_timestamp)
            self.durationDropdown.add_widget(self.writeDurationButton)
            if finished_tid is not None: 
                self.durationSelector.text = durationToText(finished_deadline-finished_timestamp)
                self.endLabel.text = localisation.get(language, "end") + " " + getDateString(finished_deadline)
            self.durationSelector.bind(on_release=self.durationDropdown.open)
            self.durationDropdown.bind(on_select=lambda instance, x: setattr(self.durationSelector, 'text', x))
            writeDurationInput = TextInput(text=durationToText(60,True), input_filter=durationInputFilter)
            self.writeDurationPopup = Popup(title=localisation.get(language, "createnew"),
            content=writeDurationInput,
            size_hint=(None, None), size=(400, 200))
            self.writeDurationButton.bind(on_release=self.writeDurationPopup.open)
            self.writeDurationPopup.bind(on_dismiss=lambda _: setattr(self.durationSelector, 'text', writeDurationInput.text))
            self.writeDurationPopup.bind(on_dismiss=self.durationDropdown.dismiss)
            popupLayout.add_widget(self.durationSelector)
            # completion time menu
            self.cooldownLabel = Label(text_size=(400, 50), font_size='12sp', valign = 'bottom', halign='left')
            popupLayout.add_widget(self.cooldownLabel)
            self.writecompletionTimeButton = Button(text=localisation.get(language, "createnew"), bold=True, color=(0.2,0.7,1,1), background_color = (0.6,0.6,0.6,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            self.completionTimeSelector = Button(text_size=(200, 100), valign = 'middle', halign='center')
            self.makeCompletionTimeDropdown(firstTask, finished_timestamp)
            self.completionTimeDropdown.add_widget(self.writecompletionTimeButton)
            if finished_tid is not None and finished_tid in MainScreen.cooldownDict: 
                self.completionTimeSelector.text = durationToText(MainScreen.cooldownDict[finished_tid])
                self.cooldownLabel.text = localisation.get(language, "cooldown") + " " + getDateString(finished_deadline+MainScreen.cooldownDict[finished_tid])
            self.completionTimeSelector.bind(on_release=self.completionTimeDropdown.open)
            self.completionTimeDropdown.bind(on_select=lambda instance, x: setattr(self.completionTimeSelector, 'text', x))
            writeCompletionTimeInput = TextInput(text=durationToText(defaultCompletionExpiration), input_filter=durationInputFilter)                         
            self.writeCompletionTimePopup = Popup(title=localisation.get(language, "createnew"),
            content=writeCompletionTimeInput,
            size_hint=(None, None), size=(400, 200))
            self.writecompletionTimeButton.bind(on_release=self.writeCompletionTimePopup.open)
            self.writeCompletionTimePopup.bind(on_dismiss=lambda _: setattr(self.completionTimeSelector, 'text', writeCompletionTimeInput.text))
            self.writeCompletionTimePopup.bind(on_dismiss=self.completionTimeDropdown.dismiss)
            popupLayout.add_widget(self.completionTimeSelector) 
            # button
            self.fightButton = None
            if finished_tid is None:
                addButton = Button(text=localisation.get(language, "go"), background_color=(0.2,0.7,1,1))                
                popupLayout.add_widget(addButton)
                addButton.bind(on_press=self.addNewTask(taskSelector, self.durationSelector, self.completionTimeSelector, popup))
            else:
                self.fightButton = Button(text=localisation.get(language, "confirm"), background_color=(1,0,0,1))
                popupLayout.add_widget(self.fightButton)
                self.fightButton.bind(on_press=self.resolveFight(finished_tid, finished_timestamp, finished_deadline, 1, self.durationSelector, self.completionTimeSelector, popup))
            # wrap it up          
            tasksDropdown.bind(on_select=lambda instance, changedTaskName:self.refreshTaskPopup(tname=changedTaskName, timestamp=finished_timestamp))
            moreTaskDropdown.bind(on_select=lambda instance, changedTaskName:self.refreshTaskPopup(tname=changedTaskName, timestamp=finished_timestamp))
            self.durationDropdown.bind(on_select=lambda instance, changedDuration:self.refreshTaskPopup(duration=changedDuration, timestamp=finished_timestamp))
            self.completionTimeDropdown.bind(on_select=lambda instance, changedCooldown:self.refreshTaskPopup(cooldown=changedCooldown, timestamp=finished_timestamp))
            self.writeDurationPopup.bind(on_dismiss=lambda _: self.refreshTaskPopup(duration=writeDurationInput.text, timestamp=finished_timestamp))
            self.writeCompletionTimePopup.bind(on_dismiss=lambda _: self.refreshTaskPopup(cooldown=writeCompletionTimeInput.text, timestamp=finished_timestamp))
            popup.open()  
            MainScreen.popups += 1
            popup.bind(on_dismiss=self.decreasePopups)
            popup.bind(on_dismiss=lambda _: self.rescheduleMainWindowReload(1)) 
        return taskPopup_inner
    
    
    def showMoreTasks(self, newDropdown, oldDropdown, parent):
        def showshowMoreTasks_inner(_=None):
            newDropdown.open(parent)
            oldDropdown.dismiss()
        return showshowMoreTasks_inner
    
    def makeDurationDropdown(self, tid, timestamp):
        if timestamp is None: timestamp = time.time()
        cur.execute("SELECT endTime, startTime FROM Fights WHERE taskID = ? AND value > 0 ORDER BY endTime DESC", [tid])
        res = cur.fetchall()
        durations = [durationToText(x[0]-x[1]) for x in res]
        seen = set()
        durations = [ x for x in durations if not (x in seen or seen.add(x))]
        self.durationDropdown = DropDown()
        firstDuration = None
        for d in durations[:10]:
            if firstDuration is None: firstDuration = d
            btn = Button(text=d, text_size=(200, 100), background_color = (0.6,0.6,0.6,1), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            btn.bind(on_release=lambda btn: self.durationDropdown.select(btn.text))
            self.durationDropdown.add_widget(btn)
        if firstDuration is None: firstDuration = durationToText(1)
        self.durationSelector.text = firstDuration
        self.endLabel.text = localisation.get(language, "end") + " " + getDateString(timestamp+ durationToInt(firstDuration) )
        
    def makeCompletionTimeDropdown(self, tid, timestamp):
        if timestamp is None: timestamp = time.time()
        cur.execute("SELECT value FROM Fights WHERE taskID = ? AND value > 0 ORDER BY endTime DESC", [tid])
        res = cur.fetchall()
        values= [durationToText(x[0]) for x in res]
        seen = set()
        values = [ x for x in values if not (x in seen or seen.add(x))]
        self.completionTimeDropdown =  DropDown()
        firstValue = None
        for v in values[:10]:
            if firstValue is None: firstValue = v
            btn = Button(text=v, background_color = (0.6,0.6,0.6,1), text_size=(200, 100), valign = 'middle', halign='center', size_hint_y=None, width = 200, height=100)
            btn.bind(on_release=lambda btn: self.completionTimeDropdown.select(btn.text))
            self.completionTimeDropdown.add_widget(btn)
        if firstValue is None: firstValue = durationToText(defaultCompletionExpiration)
        self.completionTimeSelector.text = firstValue
        self.cooldownLabel.text = localisation.get(language, "cooldown") + " " + getDateString( timestamp+durationToInt(self.durationSelector.text)+durationToInt(firstValue) )
    
    def refreshTaskPopup(self, tname=None, duration=None, cooldown=None, timestamp=None):
        if timestamp is None: timestamp = time.time()
        if tname is not None:
            try:
                tid = getTaskId(tname)
            except:
                tid = None
            self.durationDropdown.clear_widgets()
            self.makeDurationDropdown(tid, timestamp)
            self.durationDropdown.add_widget(self.writeDurationButton)
            self.durationDropdown.bind(on_select=lambda instance, x: setattr(self.durationSelector, 'text', x))
            self.durationSelector.bind(on_release=self.durationDropdown.open)       
            self.completionTimeDropdown.clear_widgets()
            self.makeCompletionTimeDropdown(tid, timestamp)
            self.completionTimeDropdown.add_widget(self.writecompletionTimeButton)
            self.completionTimeDropdown.bind(on_select=lambda instance, x: setattr(self.completionTimeSelector, 'text', x))
            self.completionTimeSelector.bind(on_release=self.completionTimeDropdown.open)
            self.durationDropdown.bind(on_select=lambda instance, changedDuration:self.refreshTaskPopup(duration=changedDuration, timestamp=timestamp))
            self.completionTimeDropdown.bind(on_select=lambda instance, changedCooldown:self.refreshTaskPopup(cooldown=changedCooldown, timestamp=timestamp))
            self.writeDurationPopup.bind(on_dismiss=self.durationDropdown.dismiss)
            self.writeCompletionTimePopup.bind(on_dismiss=self.completionTimeDropdown.dismiss)
        if duration is not None:
            self.endLabel.text = localisation.get(language, "end") + " " + getDateString( timestamp + durationToInt(duration) )
            self.cooldownLabel.text = localisation.get(language, "cooldown") + " " + getDateString( timestamp + durationToInt(duration) + durationToInt(self.completionTimeSelector.text))
            if timestamp + durationToInt(duration) > time.time() and self.fightButton is not None:
                self.endLabel.color = (1,1,0,1)
                self.endLabel.text += " !"
            elif self.fightButton is not None:
                self.endLabel.color = (1,1,1,1)                
        if cooldown is not None:
            self.cooldownLabel.text = localisation.get(language, "cooldown") + " " + getDateString( timestamp + durationToInt(self.durationSelector.text) + durationToInt(cooldown))
             
        
    def addNewTask(self, taskSelector, durationSelector, cooldownSelector=None, popup=None):
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
                duration = durationToInt(durationSelector.text) 
                cur.execute("UPDATE Fights SET value=-1 WHERE taskId=? AND value = 0 AND startTime <= ?;", [tid, time.time()])
                unComplete(tid)
                cur.execute("INSERT INTO Fights VALUES(?, ?, ?, ?)", [time.time(), time.time()+duration, 0, tid])
                con.commit() 
                MainScreen.cooldownDict[tid] = durationToInt(cooldownSelector.text)
                self.rescheduleMainWindowReload(0)
        return addNewTask_inner
               
    def resolveFight(self, task_id, timeStart, timeEnd, success, durationSelector=None, completionTimeSelector=None, popup=None):
        def resolveFight_inner(_=None):
            global waitingForResolution
            changedDeadline = timeStart + durationToInt(durationSelector.text)
            if changedDeadline <= time.time():
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
                        completionTime = durationToInt(completionTimeSelector.text)+1
                    except:
                        completionTime = 1
                    cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [completionTime, task_id, timeStart, deadline])
                    if abs(changedDeadline-deadline) > 1:
                        cur.execute("UPDATE Fights SET endTime=? WHERE taskId=? AND startTime=? AND endTime =?;", [changedDeadline, task_id, timeStart, deadline])    
                    con.commit()
                    self.makeScoreProgressPopup(task_id, oldScore)     
                elif success == -1:
                    cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [-1, task_id, timeStart, timeEnd])  
                    playAudio(soundFiles[2])
                    #Clock.schedule_once(self.taskPopup(task_id, int((timeEnd-timeStart)/60)),0)
                con.commit()
                self.rescheduleMainWindowReload(0)
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
            scoreProgress.value = oldScore % 0.1
            progressLayout.add_widget(scoreProgress)
            nextScoreMilestone = Label(text=getScoreText(oldScore, True))
            nextScoreMilestone.color = (1,1-float(nextScoreMilestone.text[:-1])/100,1-float(nextScoreMilestone.text[:-1])/100,1)
            nextScoreMilestone.bold = nextScoreMilestone.text == '100%'
            progressLayout.add_widget(nextScoreMilestone)
            scoreLayout.add_widget(progressLayout)            
            scorePopup = Popup(title=localisation.get(language, "level"),
            content=scoreLayout,
            size_hint=(None, None), size=(400, 300))
            scorePopup.open()  
            MainScreen.popups += 1
            scorePopup.bind(on_dismiss=self.decreasePopups)
            Clock.schedule_once(scorePopup.dismiss, 10)
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
                if scoreProgress.value >= 0.99*scoreProgress.max and nextScoreMilestone.text == '100%':
                    playAudio(soundFiles[5])
                if scoreProgress.value >= scoreProgress.max and not nextScoreMilestone.text == '100%':
                    if nextScoreMilestone.text == '90%':
                        playAudio(soundFiles[4])
                    else:
                        playAudio(soundFiles[3])
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