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
        print datetime.datetime.fromtimestamp(startTime).strftime('%Y-%m-%d, %H:%M'), datetime.datetime.fromtimestamp(endTime).strftime('%Y-%m-%d, %H:%M'), round(value/60/60)

with con:    
    cur = con.cursor()
    printlala()
    deleteLala()
    

   
   
    
    
    

    

            
            
        
    

