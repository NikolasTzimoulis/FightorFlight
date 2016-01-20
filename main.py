from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.dropdown import DropDown
from kivy.uix.popup import Popup
from kivy.uix.switch import Switch
from kivy.uix.scrollview import ScrollView
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.core.window import Window
import sqlite3 as lite
import time
import ConfigParser
import datetime
import math

__version__ = '2.0'
taskDB = "fof.db"
#taskDB = "/mnt/sdcard/kivy/fof/fof.db"
soundPlaylist = "sounds.m3u"
configFileName = "config.ini"
languagefile = "localisation.ini"
config = ConfigParser.ConfigParser()
# load settings from config.ini
try:
    config.read(configFileName)
    defaultCompletionExpiration = config.getint(config.sections()[0], "defaultcompletionexpiration") * 60 * 60
    language = config.get(config.sections()[0], "language")
except:
    print "Could not load config file."
    raise
    
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
    
def isRunning(tid, includepending=False):
    if includepending:
        cur.execute("SELECT COUNT(*) FROM Fights WHERE taskId = ? AND value = 0", [tid])
    else:
        cur.execute("SELECT COUNT(*) FROM Fights WHERE taskId = ? AND value = 0 AND endTime > ?", [tid, time.time()])
    if cur.fetchall()[0][0] > 0: return True
    else: return False
    
def getLastDeadline(tid):
    cur.execute("SELECT endTime FROM Fights WHERE taskId = ? AND value >=0 ORDER BY endTime DESC LIMIT 1", [tid])
    return cur.fetchall()[0][0]

def unComplete(tid):
    if isComplete(tid):
        cur.execute("SELECT endTime FROM Fights WHERE value > 0 AND taskId = ? ORDER BY endTime DESC LIMIT 1", [tid])        
        deadline = cur.fetchall()[0][0]
        cur.execute("UPDATE Fights SET value = ? WHERE taskId = ? AND endTime =  ?", [time.time() - deadline, tid, deadline])
        con.commit()
        
def getMilestones(task_id):
    cur.execute("SELECT deadline FROM Milestones WHERE taskId = ? ORDER BY deadline DESC", [task_id])
    milestones = [m[0] for m in cur.fetchall()]
    if not milestones:
        milestones.append(time.time())
    return milestones
        
def getPreviousMilestone(task_id, timeback=None):
    if timeback is None:
        timeback = time.time()
    cur.execute("SELECT deadline FROM Milestones WHERE taskId = ? AND deadline < ? ORDER BY deadline DESC LIMIT 1", [task_id, timeback])
    rows = cur.fetchall()
    if rows:
        return rows[0][0]
    cur.execute("SELECT startTime FROM Fights WHERE taskId = ? ORDER BY startTime ASC LIMIT 1", [task_id])
    rows = cur.fetchall()
    if rows:
        return rows[0][0]
    return 0

def getNextMilestone(task_id):
    cur.execute("SELECT deadline FROM Milestones WHERE taskId = ? AND deadline > ? ORDER BY deadline ASC LIMIT 1", [task_id, time.time()])
    rows = cur.fetchall()
    if rows:
        return rows[0][0]
    return time.time()

def getFirstYear(task_id):
    cur.execute("SELECT startTime FROM Fights WHERE taskId = ? ORDER BY startTime ASC LIMIT 1", [task_id])
    try:
        timestamp = cur.fetchall()[0][0]        
    except:
        timestamp = time.time()
    return datetime.datetime.fromtimestamp(timestamp).year - 1     

def getDefaultCooldown(task_id):
    cur.execute("SELECT cooldown FROM Cooldowns WHERE taskId = ?", [task_id])
    rows = cur.fetchall()
    if rows:
        return rows[0][0]
    return defaultCompletionExpiration

def setDefaultCooldown(task_id, cooldown):
    cur.execute("SELECT cooldown FROM Cooldowns WHERE taskId = ?", [task_id])
    rows = cur.fetchall()
    if rows:
        cur.execute("UPDATE Cooldowns SET cooldown = ? WHERE taskId = ?", [cooldown, task_id])
    else:
        cur.execute("INSERT INTO Cooldowns VALUES(?, ?)", [task_id, cooldown])
    con.commit()        
        
def getScore(tid, start=None, end=None, plusone = False): 
    if start is None:
        start = getPreviousMilestone(tid)
    if end is None:
        end = getNextMilestone(tid)
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

def getDateString(timestamp, includetime=True, includedate=True):
    dateFormat = ''
    if includedate:
        dateFormat += '%Y-%m-%d'
        if includetime:
            dateFormat += ', '
    if includetime:
        dateFormat += '%H:%M'
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime(dateFormat)
    except:
        return '???'   

def calculateHeight(d):
    return 10+20*math.log(d/100+1)
  
def commitConfig():
    config.set(config.sections()[0], "language", language)
    configFile = open(configFileName, 'w')
    config.write(configFile)
    configFile.close()

def playAudio(filename):
    sound = SoundLoader.load(filename)
    if sound: sound.play()
    
class MainScreen(ScrollView):
    
    nextReload = None
    showall = False

    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        Window.bind(on_keyboard=self.Android_back_click)
        self.size_hint=(None, None)
        self.size=(Window.width, Window.height)
        self.pos_hint={'center_x':.5, 'center_y':.5}
        self.buildMainScreen()      

    def Android_back_click(self,window,key,*largs):
        if key == 27:
            self.buildMainScreen()   
            return True
        
    def buildMainScreen(self, _=None):
        self.clear_widgets()
        mainLayout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        mainLayout.bind(minimum_height=mainLayout.setter('height'))
        self.scroll_y = 1
        self.add_widget(mainLayout)
        cur.execute("SELECT DISTINCT taskId, endTime FROM Fights WHERE value = 0")
        runningTaskDeadlines = {}
        for r in cur.fetchall():
            runningTaskDeadlines[r[0]] = r[1]
        runningTasks = runningTaskDeadlines.keys()
        runningTasks.sort(key = lambda tid: runningTaskDeadlines[tid], reverse = False)
        cur.execute("SELECT DISTINCT taskId FROM Milestones WHERE deadline >= ?", [time.time()])
        tasks = [t[0] for t in cur.fetchall()]
        if tasks and not MainScreen.showall:
            tasks.sort(key = lambda tid: getCompletionExpirationDate(tid), reverse = False)
        else:
            MainScreen.showall = True
            cur.execute("SELECT id FROM Tasks")
            tasks = [x[0] for x in cur.fetchall()]
            tasks.sort(key = lambda tid: getScore(tid), reverse = True)
        tasks = [t for t in tasks if t not in runningTasks]
        tasks = runningTasks + tasks
        self.progressbars = []
        for tid in tasks:
            running = isRunning(tid, True)
            completed = isComplete(tid)
            taskLayout = GridLayout(cols=2, spacing=0, size_hint_y=None, height=100)
            mainLayout.add_widget(taskLayout)
            taskButton = Button(text=getTaskName(tid),  size_hint_y=None, height=100)
            taskLayout.add_widget(taskButton)   
            pledgeButton = Button(size_hint_y=None, size_hint_x=None, width=100, height=100)
            taskLayout.add_widget(pledgeButton)
            pledgeButton.background_color = (0,1,0,1)      
            taskButton.bind(on_press=self.taskMenu(tid))
            if running:
                taskButton.background_color = (0.8,1,0.8,1)
                pledgeButton.background_color = (1,0,0,1)
                cur.execute("SELECT startTime, endTime FROM Fights WHERE value = 0 AND taskId = ?",[tid])
                startTime, endTime = cur.fetchall()[0]
                pledgeButton.bind(on_press=self.taskPopup(tid,  startTime, endTime, True))
                taskProgress = ProgressBar(max=endTime-startTime)
                self.progressbars.append(taskProgress)
                mainLayout.add_widget(taskProgress)
                timeLeft = endTime - time.time()
                if timeLeft > 0: 
                    taskProgress.value = (min(time.time()-startTime, endTime-startTime+1))
                else: 
                    taskProgress.max = taskProgress.value = 1
            else:
                pledgeButton.bind(on_press=self.taskPopup(tid))
                if completed:
                    taskButton.background_color = (1,0.8,0.8,1)        
                    
        if not MainScreen.showall:
            moreButton = Button(text=localisation.get(language,"showmore"), bold=True, size_hint_y=None, height=100)
            mainLayout.add_widget(moreButton)
            moreButton.bind(on_press=self.toggleTasksShown)
        else:
            writeTaskInput = TextInput(text='')
            writeTaskPopup = Popup(title=localisation.get(language, "createnew"),
            content=writeTaskInput,
            size_hint=(None, None), size=(400, 200))
            writeTaskPopup.bind(on_dismiss=self.addEmptyTask(writeTaskInput))
            newTaskButton = Button(text=localisation.get(language,"createnew"), bold=True, size_hint_y=None, height=100)
            newTaskButton.bind(on_release=writeTaskPopup.open)
            mainLayout.add_widget(newTaskButton)
            langDropdown = DropDown()
            for lang in localisation.sections():
                btn = Button(text=lang,background_color = (0.6,0.6,0.6,1), valign = 'middle', halign='center', size_hint_y=None, height=100)
                btn.bind(on_release=self.changeLanguage(lang))
                btn.bind(on_release=langDropdown.dismiss)
                langDropdown.add_widget(btn)
            langButton = Button(text=localisation.get(language,"language"), bold=True, size_hint_y=None, height=100)
            langButton.bind(on_press=langDropdown.open)
            mainLayout.add_widget(langButton)
            lessButton = Button(text=localisation.get(language,"showless"), bold=True, size_hint_y=None, height=100)                        
            mainLayout.add_widget(lessButton)
            lessButton.bind(on_press=self.toggleTasksShown)
                                                
        Clock.unschedule(self.incrementProgressBars)
        Clock.schedule_interval(self.incrementProgressBars, 1)     
        
    def changeLanguage(self, newLanguage):
        def changeLanguage_inner(_=None):
            global language
            language = newLanguage
            self.buildMainScreen()
            commitConfig()   
        return changeLanguage_inner
        
    def addEmptyTask(self, taskInput):
        def addEmptyTask_inner(_):
            if taskInput.text:
                try:               
                    cur.execute("INSERT INTO Tasks(name) VALUES(?)", [taskInput.text.strip()])
                except:
                    cur.execute("INSERT INTO Tasks(name) VALUES(?)", [taskInput.text.strip().decode('utf-8')])
            con.commit()
            self.buildMainScreen()
        return addEmptyTask_inner        
        
    def toggleTasksShown(self, _):
        if MainScreen.showall: 
            MainScreen.showall = False
        else:
            MainScreen.showall = True
        self.buildMainScreen()
    
    def incrementProgressBars(self, dt): 
        for pb in self.progressbars:
            if pb.value == pb.max-1: playAudio(soundFiles[1]) 
            pb.value+=1
            
    def taskMenu(self, tid, oldScore=None):
        def taskMenu_inner(_=None):
            self.clear_widgets()
            taskMenuLayout = GridLayout(cols=1, spacing=10, size_hint_y=None)
            taskMenuLayout.bind(minimum_height=taskMenuLayout.setter('height'))
            self.scroll_y = 1
            self.add_widget(taskMenuLayout)
            backButton = Button(text=getTaskName(tid), size_hint_y=None, height=100)
            statusLabel = Label(font_size='12sp', valign = 'top', halign='left')
            if isRunning(tid, True):
                backButton.background_color = (0.8,1,0.8,1)
                statusLabel.text = localisation.get(language, "end") + " " + getDateString(getLastDeadline(tid)) 
            elif isComplete(tid):
                backButton.background_color = (1,0.8,0.8,1)
                statusLabel.text = localisation.get(language, "cooldown") + " " + getDateString(getCompletionExpirationDate(tid))
            else:
                statusLabel.text = localisation.get(language, "limbo") + " " + getDateString(getCompletionExpirationDate(tid))
            backButton.bind(on_press=self.buildMainScreen)
            taskMenuLayout.add_widget(backButton)
            taskMenuLayout.add_widget(statusLabel)
            for milestone in getMilestones(tid):  
                taskMenuLayout.add_widget(self.makeMilestoneLayout(tid, milestone, oldScore if milestone == getNextMilestone(tid) else None))
            newMilestoneButton = Button(text=localisation.get(language,"newdate"), bold=True, size_hint_y=None, height=100)
            taskMenuLayout.add_widget(newMilestoneButton)
            newMilestoneButton.bind(on_press=self.mileStonePopup(tid))
            delConfirmSwitch =  Switch()
            delConfirmPopup = Popup(title=localisation.get(language, "sure"),
            content=delConfirmSwitch,
            size_hint=(None, None), size=(200, 200))
            delConfirmPopup.bind(on_dismiss=self.deleteTask(tid, delConfirmSwitch))
            delButton = Button(text=localisation.get(language,"deltask"), bold=True, size_hint_y=None, height=100)
            delButton.bind(on_press=delConfirmPopup.open)            
            taskMenuLayout.add_widget(delButton)
        return taskMenu_inner
    
    def makeMilestoneLayout(self, tid, milestone = None, oldScore=None):
        milestone2 = getPreviousMilestone(tid, milestone)
        newScore = getScore(tid, milestone2, milestone)
        if oldScore is None:
            oldScore = newScore
        scoreLayout = GridLayout(cols=1, spacing=10, size_hint_y = None)
        milestoneButton = Button(text=getDateString(milestone, False), font_size='16sp', size_hint_y = None, height=50)
        milestoneButton.bind(on_press=self.milestoneMenu(tid, milestone))
        scoreLayout.add_widget(milestoneButton)
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
        Clock.schedule_interval(self.incrementScoreProgress(scoreProgress, prevScoreMilestone, nextScoreMilestone, oldScore, newScore), 0.1)
        scoreLayout.add_widget(progressLayout)
        scoreLabel = Label(text=str(int(100*newScore))+"%")
        if getNextMilestone(tid) == milestone:
            #expScore = newScore * (milestone-time.time()) / (time.time()-milestone2)
            idealScore = newScore + (milestone-time.time())/(milestone-milestone2)            
            scoreLabel.text += ' ('+ str(int(100*idealScore))+"%)"
        scoreLabel.color = (1,1-newScore,1-newScore,1)
        scoreLabel.bold = newScore>=0.99
        scoreLayout.add_widget(scoreLabel)
        return scoreLayout
            
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
    
    def milestoneMenu(self, tid, milestone):
        def milestoneMenu_inner(_=None):
            self.clear_widgets()
            milestoneMenuLayout = GridLayout(cols=1, spacing=10, size_hint_y=None)
            milestoneMenuLayout.bind(minimum_height=milestoneMenuLayout.setter('height'))
            self.scroll_y = 1
            self.add_widget(milestoneMenuLayout)
            milestone2 = getPreviousMilestone(tid, milestone)
            backButton = Button(size_hint_y=None, height=100, halign='center')
            backButton.text = getTaskName(tid)+ '\n' + getDateString(milestone2, False) + ' - ' + getDateString(milestone, False)
            backButton.bind(on_press=self.taskMenu(tid))
            milestoneMenuLayout.add_widget(backButton)
            cur.execute("SELECT startTime, endTime, value FROM Fights WHERE taskId = ? AND endTime + value > ? AND startTime < ? ORDER BY endTime + value DESC", [tid, milestone2, milestone])
            for startTime, endTime, value in cur.fetchall():
                if value > 1:
                    cooldownButton = Button(text=getDateString(endTime+value), background_color=(1,0,0,1), height=calculateHeight(value), size_hint_y=None, valign='top')
                    milestoneMenuLayout.add_widget(cooldownButton)
                pledgeButton = Button(text=getDateString(endTime), background_color=(0,1,0,1), height=calculateHeight(endTime-startTime), size_hint_y=None)
                if endTime-startTime >= 120:    
                    pledgeButton.text += '\n'+getDateString(startTime)
                milestoneMenuLayout.add_widget(pledgeButton)
            delButton = Button(text=localisation.get(language,"deltask"), bold=True, size_hint_y=None, height=100)
            delButton.bind(on_press=self.deleteMilestone(tid, milestone))      
            milestoneMenuLayout.add_widget(delButton)      
        return milestoneMenu_inner
    
    def deleteMilestone(self, task_id, milestone):
        def deleteMilestone_inner(_=None):
            cur.execute("DELETE FROM Milestones WHERE taskId = ? AND deadline = ?", [task_id, milestone])
            con.commit()
            self.taskMenu(task_id)()
        return deleteMilestone_inner
    
    def mileStonePopup(self, tid):
        def mileStonePopup_inner(_,__=None):
            popupLayout = BoxLayout(orientation='horizontal')
            popup = Popup(title=localisation.get(language,"newdate"),
            content=popupLayout,
            size_hint=(None, None), size=(400, 200))
            yearSelector = Button(text_size=(400, 100), valign = 'middle', halign='center')
            popupLayout.add_widget(yearSelector)
            monthSelector = Button(text_size=(400, 100), valign = 'middle', halign='center')
            popupLayout.add_widget(monthSelector)
            daySelector = Button(text_size=(400, 100), valign = 'middle', halign='center')
            popupLayout.add_widget(daySelector)
            yearDropdown = DropDown()
            yearSelector.bind(on_release=yearDropdown.open)
            yearDropdown.bind(on_select=lambda instance, x: setattr(yearSelector, 'text', x))
            firstYear = getFirstYear(tid)
            for year in range(firstYear,firstYear+101):
                if yearSelector.text == '': yearSelector.text = str(year)
                btn = Button(text=str(year),background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)
                btn.bind(on_release=lambda btn: yearDropdown.select(btn.text))
                yearDropdown.add_widget(btn)
            monthDropdown = DropDown()
            monthSelector.bind(on_release=monthDropdown.open)
            monthDropdown.bind(on_select=lambda instance, x: setattr(monthSelector, 'text', x))
            for month in range(1,12+1):
                if monthSelector.text == '': monthSelector.text = str(month)
                btn = Button(text=str(month),background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)
                btn.bind(on_release=lambda btn: monthDropdown.select(btn.text))
                monthDropdown.add_widget(btn)
            dayDropdown= DropDown()
            daySelector.bind(on_release=dayDropdown.open)
            dayDropdown.bind(on_select=lambda instance, x: setattr(daySelector, 'text', x))
            for day in range(1,31+1):
                if daySelector.text == '': daySelector.text = str(day)
                btn = Button(text=str(day),background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)
                btn.bind(on_release=lambda btn: dayDropdown.select(btn.text))
                dayDropdown.add_widget(btn)
            popup.bind(on_dismiss=self.addMilestone(tid, yearSelector, monthSelector, daySelector))
            popup.open()
        return mileStonePopup_inner 
            
    def taskPopup(self, original_tid = None, original_timestamp = None, original_deadline = None, finished=False):
        def taskPopup_inner(_,__=None):
            popupLayout = BoxLayout(orientation='vertical')
            popup = Popup(title=localisation.get(language,"newtask"),
            content=popupLayout,
            size_hint=(None, None), size=(800, 800))
            # task selection menu
            tasksDropdown = DropDown()
            moreTaskDropdown =  DropDown()
            cur.execute("SELECT DISTINCT taskID FROM Fights WHERE value > 0")
            tasks = [x[0] for x in cur.fetchall()]
            firstTask = original_tid
            for tid in sorted(tasks, key=lambda x:getScore(x), reverse=True):
                #print getTaskName(tid), score
                btn = Button(text=getTaskName(tid), background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)                
                if not isComplete(tid) and not isRunning(tid) and getNextMilestone(tid) > time.time():
                    if firstTask is None: firstTask = tid
                    tasksDropdown.add_widget(btn) 
                    btn.bind(on_release=lambda btn: tasksDropdown.select(btn.text)) 
                else:
                    btn.bind(on_release=lambda btn: moreTaskDropdown.select(btn.text))
                    moreTaskDropdown.add_widget(btn)                
            moreTasksButton = Button(text=localisation.get(language, "showmore"), bold=True, background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)
            writeTaskButton = Button(text=localisation.get(language, "createnew"), bold=True, background_color = (0.6,0.6,0.6,1), text_size=(400, 100), valign = 'middle', halign='center', size_hint_y=None, width = 400, height=100)
            tasksDropdown.add_widget(moreTasksButton)
            moreTaskDropdown.add_widget(writeTaskButton)
            taskSelector = Button(text=getTaskName(firstTask), text_size=(400, 100), valign = 'middle', halign='center')
            if not finished: taskSelector.bind(on_release=tasksDropdown.open)
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
            self.makeDurationDropdown(firstTask, original_timestamp)
            self.durationDropdown.add_widget(self.writeDurationButton)
            if finished:
                if original_deadline <= time.time(): 
                    self.durationSelector.text = durationToText(original_deadline-original_timestamp)
                    self.endLabel.text = localisation.get(language, "end") + " " + getDateString(original_deadline)
                else:
                    self.durationSelector.text = durationToText(time.time()-original_timestamp)
                    self.endLabel.text = localisation.get(language, "end") + " " + getDateString(time.time())
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
            self.makeCompletionTimeDropdown(firstTask, original_timestamp)
            self.completionTimeDropdown.add_widget(self.writecompletionTimeButton)
            defaultCooldown = getDefaultCooldown(original_tid)
            if finished: 
                self.completionTimeSelector.text = durationToText(defaultCooldown)
                if original_deadline <= time.time(): 
                    self.cooldownLabel.text = localisation.get(language, "cooldown") + " " + getDateString(original_deadline+defaultCooldown)
                else:
                    self.cooldownLabel.text = localisation.get(language, "cooldown") + " " + getDateString(time.time()+defaultCooldown)
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
            if not finished:
                addButton = Button(text=localisation.get(language, "go"), background_color=(0,1,0,1))                
                popupLayout.add_widget(addButton)
                addButton.bind(on_press=self.addNewPledge(taskSelector, self.durationSelector, self.completionTimeSelector, popup))
            else:
                self.fightButton = Button(text=localisation.get(language, "confirm"), background_color=(1,0,0,1))
                popupLayout.add_widget(self.fightButton)
                self.fightButton.bind(on_press=self.resolveFight(original_tid, original_timestamp, original_deadline, 1, self.durationSelector, self.completionTimeSelector, popup))
            # wrap it up          
            tasksDropdown.bind(on_select=lambda instance, changedTaskName:self.refreshTaskPopup(tname=changedTaskName, timestamp=original_timestamp))
            moreTaskDropdown.bind(on_select=lambda instance, changedTaskName:self.refreshTaskPopup(tname=changedTaskName, timestamp=original_timestamp))
            self.durationDropdown.bind(on_select=lambda instance, changedDuration:self.refreshTaskPopup(duration=changedDuration, timestamp=original_timestamp))
            self.completionTimeDropdown.bind(on_select=lambda instance, changedCooldown:self.refreshTaskPopup(cooldown=changedCooldown, timestamp=original_timestamp))
            self.writeDurationPopup.bind(on_dismiss=lambda _: self.refreshTaskPopup(duration=writeDurationInput.text, timestamp=original_timestamp))
            self.writeCompletionTimePopup.bind(on_dismiss=lambda _: self.refreshTaskPopup(cooldown=writeCompletionTimeInput.text, timestamp=original_timestamp))
            popup.open()  
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
             
        
    def addNewPledge(self, taskSelector, durationSelector, cooldownSelector=None, popup=None):
        def addNewPledge_inner(_=None):
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
                setDefaultCooldown(tid, durationToInt(cooldownSelector.text))
                self.buildMainScreen()
        return addNewPledge_inner
               
    def resolveFight(self, task_id, timeStart, timeEnd, success, durationSelector=None, completionTimeSelector=None, popup=None):
        def resolveFight_inner(_=None):
            global waitingForResolution
            changedDeadline = timeStart + durationToInt(durationSelector.text)
            if changedDeadline <= time.time():
                if popup is not None: popup.dismiss()
                oldScore = getScore(task_id, getPreviousMilestone(task_id), getNextMilestone(task_id))
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
                elif success == -1:
                    cur.execute("UPDATE Fights SET value=? WHERE taskId=? AND startTime=? AND endTime =?;", [-1, task_id, timeStart, timeEnd])  
                    playAudio(soundFiles[2])
                    #Clock.schedule_once(self.taskPopup(task_id, int((timeEnd-timeStart)/60)),0)
                con.commit()
                self.taskMenu(task_id, oldScore)()
        return resolveFight_inner       
    
    def addMilestone(self, task_id, yearSelector, monthSelector, daySelector):
        def addMilestone_inner(_=None):
            milestone = datetime.datetime(int(yearSelector.text), int(monthSelector.text), int(daySelector.text))
            timestamp = (milestone - datetime.datetime(1970, 1, 1)).total_seconds() 
            cur.execute("INSERT INTO Milestones VALUES(?, ?)", [task_id, timestamp])
            con.commit()
            self.taskMenu(task_id)()
        return addMilestone_inner
    
    def deleteTask(self, task_id, switch):
        def deleteTask_inner(_=None):
            if switch.active:
                cur.execute("DELETE FROM Fights WHERE taskId = ?", [task_id])
                cur.execute("DELETE FROM Cooldowns WHERE taskId = ?", [task_id])
                cur.execute("DELETE FROM Milestones WHERE taskId = ?", [task_id])
                cur.execute("DELETE FROM Tasks WHERE id = ?", [task_id])
                con.commit()
                self.buildMainScreen()
        return deleteTask_inner
    
    

class FoFApp(App):
    def build(self):
        self.mainScreen = MainScreen()
        return self.mainScreen
        
    def on_pause(self):
        # Here you can save data if needed
        self.mainScreen.buildMainScreen()
        return True

    def on_resume(self):
        # Here you can check if any data needs replacing (usually nothing)
        pass

# load audio
soundFiles = []
for line in open(soundPlaylist):
    soundFiles.append(line.strip()) 

# set up database if it does not already exist
con = lite.connect(taskDB)
with con:    
    cur = con.cursor()
    try:
        cur.execute("CREATE TABLE Milestones(taskId INTEGER, deadline INTEGER, FOREIGN KEY(taskId) REFERENCES Tasks(id));")
        cur.execute("CREATE TABLE Cooldowns(taskId INTEGER, cooldown INTEGER, FOREIGN KEY(taskId) REFERENCES Tasks(id));")
        cur.execute("CREATE TABLE Tasks(id INTEGER PRIMARY KEY, name TEXT UNIQUE);")
        cur.execute("CREATE TABLE Fights(startTime INTEGER, endTime INTEGER, value INTEGER, taskId INTEGER, FOREIGN KEY(taskId) REFERENCES Tasks(id));")
        print 'Created new database.'
    except:
        print 'Found existing database.'

if __name__ == '__main__':
    FoFApp().run()