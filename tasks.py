from datetime import datetime, timedelta
import os, time, codecs

tasksPath = 'C:\\Users\\Nikolas\\Dropbox\\public\\tasks.txt'
resultsPath =  'C:\\Users\\Nikolas\\Documents\\time stats.txt'

tasksFile = codecs.open(tasksPath, encoding='utf-8')

storyTimes = {}

currentStory = ''
currentDeadline = datetime.now() 
currentDeadline += timedelta(hours = 23 - currentDeadline.hour, minutes = 59 - currentDeadline.minute, seconds = 59 - currentDeadline.second)
storyTimes[currentDeadline] = {}
for line in tasksFile:
    line = line.lstrip(codecs.BOM_UTF8.decode('utf8'))
    line = line.strip()
    if line.startswith('['):
        endNum = line.find(']')
        taskTime = int( line[1:endNum] )
        storyTimes[currentDeadline][currentStory] += taskTime
    elif line.endswith(':'):
        currentDeadline = datetime.strptime(line[:-1], '%d/%m/%Y') + timedelta(hours = 23, minutes = 59, seconds = 59)        
        storyTimes[currentDeadline] = {}
    else:
        currentStory = line
        storyTimes[currentDeadline][currentStory] = 0

tasksFile.close()
resultsFile = open(resultsPath, 'w')

timeStart = datetime.now()
for deadline in sorted(storyTimes.keys()):
    if len(storyTimes[deadline]) == 0:
        continue
    totalTime = 0
    timeDiff = deadline - timeStart
    hoursLeft = timeDiff.total_seconds() / 3600
    if len(storyTimes[deadline]) > 0: resultsFile.write((deadline.strftime('%d/%m/%Y')+'\n').encode('utf-8'))
    for story in storyTimes[deadline]:
        if storyTimes[deadline][story] > 0:
            line = '\t'+story+': '
            line += str(storyTimes[deadline][story]) + ' hours ('
            if hoursLeft >= 24:
                line += str(round(24*storyTimes[deadline][story]/hoursLeft,1)) + ' hours per day , '
            line += str(round(100*storyTimes[deadline][story]/hoursLeft,1)) + '% load)\n'
            resultsFile.write(line.encode('utf-8'))
            totalTime += storyTimes[deadline][story]
    line = '\tTotal: '
    line += str(totalTime) + ' hours ('
    if hoursLeft >= 24:
        line += str(round(24*totalTime/hoursLeft,1)) + ' hours per day , '
    line += str(round(100*totalTime/hoursLeft,1)) + '% load)\n'
    if len(storyTimes[deadline]) > 0: resultsFile.write(line.encode('utf-8'))
    timeStart = deadline
        

resultsFile.close()
time.sleep(1)
os.startfile(resultsPath)