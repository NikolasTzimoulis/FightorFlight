# Kivy
###Main Screen
* On the upper half of the screen you can watch the progress of the currently running pledges. When a pledge is finished, you will be taken to the **Fight or Flight Screen**.
* On the bottom half of the screen you can press the blue **+** button and you will be taken to the **New Pledge Screen**.

###Fight or Flight Screen
* Press the red button if the pledge was successful. Select the desired cooldown time (in hours) for the task from the dropdown menu and press the red button next to it to cofirm. Your progress with the task will be briefly shown.
* You can enter a custom cooldown by using the blue **+** item on the dropdown menu. Enter the cooldown time in the text field that will appear and tap anywhere outside the text field to save.
* Press the grey button if the pledge was a failure.

###New Pledge Screen
* Use the dropdown menu on the left to change the task. Select the desired running time (in minutes) on the dropdown menu in the middle. Finally press the blue **+** button on the right to start the pledge. 
* The task dropdown menu is populated with recently active tasks that are not currently on cooldown. Select the **...** item on the task dropdown menu to open an extension dropdown menu that will be populated with all the remaining tasks. 
* You can create a new task by using the blue **+** item on the extension dropdown menu. Enter the name of the new task in the text field that will appear and tap anywhere outside the text field to save.
* You can enter a custom running time by using the blue **+** item on the running time dropdown menu. Enter the running time in the text field that will appear and tap anywhere outside the text field to save.

-----
# Tkinter
###Text Field
* Type **taskname time** in the text field then press ENTER to create new pledge. A Task Progressbar will show up.
* Press UP or DOWN arrows in the text field to get suggestions from pledges that occured around the same time in previous days. Only suggestions for the main task will show if the main task is not on cooldown or currently running.
* Right-click in the text field to view Recent Tasks.
* Type a **time** and press ENTER to change the time window.
* **time** is **days:hours:minutes** but you can omit days and hours if you want.

###Recent Tasks
* Currently running tasks show in green font.
* Tasks on cooldown show in red font.
* The tasks that should be focused on show with a white background.
* Triple right-click on a task to add it or remove it from the tasks that should be focused.
* Click on a task to re-schedule its last successful pledge in the Text Field.
* Triple middle-click on a task to delete the last successful pledge of this task.
* A square will appear next to tasks on cooldown, indicating the task's overall score.
* Click on the square to get a successful pledges chart for the past time window.

###Pledge Progressbar
* Progress bar shows how close you are to the end of the pledge.
* Click anywhere on the Pledge Progressbar to re-schedule the pledge in the Text Field.
* Triple-click on the Pledge Progressbar to prematurely finish the task successfully.
* Once the time is up, the progressbar will be replaced by the Fight or Flight Buttons.

###Fight or Flight Buttons
* Click on the check mark if the pledge was successful. The task will go on cooldown.
* Before clicking the check mark, type a **time** in the Text Field to change the cooldown duration.
* Click on the x mark if the pledge was not succesful.
* Next to the buttons, you can see a square indicating the task's overall score for the past time window.
* Click on the square to get a successful pledges chart for the past time window.
	
	