from datetime import datetime, timedelta
import os, time, codecs

tasksPath = 'C:\\Users\\Nikolas\\Dropbox\\tasks.txt'
resultsPath =  'C:\\Users\\Nikolas\\Documents\\time stats.txt'

tasksFile = codecs.open(tasksPath, encoding='utf-8')

speed = float(raw_input('Speed:'))

storyNames = []
storyTimes = []
for line in tasksFile:
    line = line.lstrip(codecs.BOM_UTF8.decode('utf8'))
    line = line.strip()
    if line.startswith('['):
        endNum = line.find(']')
        taskTime = int( line[1:endNum] )
        storyTimes[-1] += taskTime
    else:
        storyNames.append(line)
        storyTimes.append(0)

tasksFile.close()
resultsFile = open(resultsPath, 'w')

timeStart = datetime.now()
days = 0.0
for story in range(len(storyNames)):
    days += storyTimes[story] / speed
    deadline = timeStart + timedelta(days=days)
    line = deadline.strftime('%d/%m/%Y')+': ' 
    line += storyNames[story]
    line += ' ('+str(storyTimes[story])+')\n'
    resultsFile.write(line.encode('utf-8'))
        

resultsFile.close()
time.sleep(1)
os.startfile(resultsPath)