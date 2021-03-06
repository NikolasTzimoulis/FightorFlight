import sqlite3 as lite
import time
import datetime
import encodings


taskDB = "fof.db"
con = lite.connect(taskDB)

def remakeDatabase():
    cur.execute("CREATE TABLE Tasks(id INTEGER PRIMARY KEY, name TEXT UNIQUE, complete INTEGER);")
    cur.execute("CREATE TABLE Fights(startTime INTEGER, endTime INTEGER, value INTEGER, taskId INTEGER, FOREIGN KEY(taskId) REFERENCES Tasks(id));")
    cur.execute("SELECT id, name, complete FROM Tasks ORDER BY complete")
    
def dropColumn():
    cur.execute("CREATE TEMPORARY TABLE Tasks_backup(id INTEGER PRIMARY KEY, name TEXT UNIQUE);")
    cur.execute("INSERT INTO Tasks_backup SELECT id,name FROM Tasks;")
    cur.execute("DROP TABLE Tasks;")
    cur.execute("CREATE TABLE Tasks(id INTEGER PRIMARY KEY, name TEXT UNIQUE);")
    cur.execute("INSERT INTO Tasks SELECT id,name FROM Tasks_backup;")
    cur.execute("DROP TABLE Tasks_backup;")
    
def fixExpirationDates():
    cur.execute("SELECT * FROM Tasks")
    for tid, tname in cur.fetchall():
        print tid, tname
        cur.execute("SELECT startTime, endTime, value FROM Fights WHERE value > 0 AND taskId = ? ORDER BY endTime DESC", [tid])
        nextStartTime = float('inf')
        for startTime, endTime, value in cur.fetchall():
            if endTime + value > nextStartTime:
                print endTime, '+', value, '>', nextStartTime
                newVal = nextStartTime-endTime
                cur.execute("UPDATE Fights SET value = ? WHERE startTime = ? AND endTime = ? AND taskId = ?", [newVal, startTime, endTime, tid])            
            nextStartTime = startTime
            
def deleteLala():
    cur.execute("DELETE FROM Fights WHERE taskID = (SELECT id FROM Tasks WHERE name LIKE 'lala%')")
    cur.execute("DELETE FROM Tasks WHERE name LIKE 'lala%'")
    
def printlala():
    cur.execute("SELECT * FROM Fights WHERE taskID = (SELECT id FROM Tasks WHERE name LIKE 'lala%')")
    for startTime, endTime, value, tid in cur.fetchall():
        cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
        print cur.fetchall()[0][0], datetime.datetime.fromtimestamp(startTime).strftime('%Y-%m-%d, %H:%M'), datetime.datetime.fromtimestamp(endTime).strftime('%Y-%m-%d, %H:%M'), round(value/60/60)

def findWeirdEntries():
    cur.execute("SELECT * FROM Fights WHERE endTime > 1544486400")
    for startTime, endTime, value, tid in cur.fetchall():
        cur.execute("SELECT name FROM Tasks WHERE id = ?", [tid])
        print cur.fetchall()[0][0], datetime.datetime.fromtimestamp(startTime).strftime('%Y-%m-%d, %H:%M'), datetime.datetime.fromtimestamp(endTime).strftime('%Y-%m-%d, %H:%M'), round(value/60/60), startTime
        
def resetTable(tableName):        
    cur.execute("DELETE FROM "+tableName)
    print(tableName+" deleted rows.")
    
def deleteTable(tableName):
    cur.execute("DROP TABLE "+tableName)
    print(tableName+" deleted.")
    
def printTasks():
    cur.execute("SELECT id, name FROM Tasks")
    for tid, tname in cur.fetchall():
        print tid, tname

def printMilestones(task_id):
    cur.execute("SELECT deadline FROM Milestones WHERE taskId = ?", [task_id])
    for milestone in cur.fetchall():
        print datetime.datetime.fromtimestamp(milestone[0]).strftime('%Y-%m-%d, %H:%M')

def printAllMilestones():
    cur.execute("SELECT * FROM Milestones")
    for tid, milestone in cur.fetchall():
        print tid, datetime.datetime.fromtimestamp(milestone).strftime('%Y-%m-%d, %H:%M')

def printSchema(table):
    cur.execute("PRAGMA table_info("+table+");")
    for col in cur.fetchall():
        print col
        
def integrity():
    cur.execute("pragma integrity_check")
    for la in cur.fetchall():
        print la
        
def timeActive(tid):
    cur.execute("SELECT SUM(endTime-startTime) FROM Fights WHERE taskId = ?", [tid])
    print cur.fetchall()[0][0]/60/60
    
def fixTime(tid, old, new):
    cur.execute("UPDATE Fights SET startTime = ?, endTime = ? WHERE startTime = ? AND endTime = ? AND taskId = ?", [new, new, old, old, tid])
    
def latest(task, limit):
    cur.execute("SELECT startTime, endTime, value FROM Fights WHERE taskId = ? ORDER BY endTime DESC LIMIT ?", [task, limit])
    for starttime, endtime, val, in cur.fetchall():
        print datetime.datetime.fromtimestamp(starttime).strftime('%Y-%m-%d, %H:%M'), 
        print datetime.datetime.fromtimestamp(endtime).strftime('%Y-%m-%d, %H:%M')
        print val, datetime.datetime.fromtimestamp(endtime+val).strftime('%Y-%m-%d, %H:%M'), "\n"
        
def newFight(start, end, value, task):
    cur.execute("INSERT INTO Fights VALUES(?, ?, ?, ?)", [start, end, value, task])
    
with con:    
    cur = con.cursor()
    #newFight(, , , 16)

    printTasks()
    
    
   
    
    
    

    

            
            
        
    

