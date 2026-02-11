steps:
1. clone repo using git clone https://github.com/harshabose/thrust_stand.git
2. create virtual environment inside the directory (thrust_stand) python3.x -m .venv venv
3. activate the virtual environment:<br>
1.unix-like systems:<br>
  `source .venv/bin/activate`<br>
2. windows:<br>
  `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`<br>
  `\.venv\Scripts\Activate.ps1`
4. install dependencies<br>
   `pip3 install -r requirements.txt`
5. change config in `main.py` as needed.
6. run the code<br>
   `python3.x main.py`
<br>
this should also start a GUI (ask vishak about this). if there are some errors, instead of running the `main.py`, just run `thrust_stand/strategies/stepper_uo_down.py` for no GUI

