steps:
1. clone repo using git clone https://github.com/harshabose/thrust_stand.git
2. create virtual environment inside the directory (thrust_stand) python3.x -m .venv venv
3. activate the virtual environment:
unix-like systems:
  `source .venv/bin/activate`
windows:
  `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
  `\.venv\Scripts\Activate.ps1`
4. install dependencies
   `pip3 install -r requirements.txt`
5. change config in `main.py` as needed.
6. run the code
   `python3.x main.py`

this should also start a GUI (ask vishak about this). if there are some errors, instead of running the `main.py`, just run `thrust_stand/strategies/stepper_uo_down.py` for no GUI

