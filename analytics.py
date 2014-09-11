import win32com.client
import sqlite3 as lite
import time
import datetime
import os

analyticsFileName = "analytics.txt"
regressionScript = "gp_play"
chartFilename = "analytics.png"
taskDB = "fof.db"
timeUnit = 24*60*60 # one day in seconds

con = lite.connect(taskDB)
cur = con.cursor()
cur.execute("SELECT MIN(endTime) FROM Fights", [])
beginning = cur.fetchall()[0][0]
timeCounter = time.time()
table = []
while timeCounter > beginning:
    cur.execute("SELECT SUM(value) FROM Fights WHERE value = 1 AND endTime >= ? AND endTime < ?", [timeCounter-timeUnit, timeCounter])
    sumFights = cur.fetchall()[0][0]
    cur.execute("SELECT SUM(value) FROM Fights WHERE value = -1 AND endTime >= ? AND endTime < ?", [timeCounter-timeUnit, timeCounter])
    sumFlights = cur.fetchall()[0][0]
    table.append(map(lambda x: x if not x==None else 0, [timeCounter, sumFights, sumFlights]))
    timeCounter -= timeUnit
table.reverse()
con.close()

analyticsFile = open(analyticsFileName, 'w')
analyticsFile.write('\n'.join(datetime.datetime.fromtimestamp(int(t[0])).strftime('%d/%m/%Y')+"\t"+str(t[1])+"\t"+str(t[2]) for t in table))
analyticsFile.close()
#os.startfile(regressionFileName)
h = win32com.client.Dispatch('matlab.application')
print h.Execute("cd('"+os.getcwd()+"')")
print h.Execute (regressionScript)
os.startfile(chartFilename)