import os
import subprocess

user_input = input()
eval(user_input)
exec(user_input)
os.system(user_input)
subprocess.run(user_input, shell=True)
