import json
import subprocess

user_input = input()
json.loads(user_input)
subprocess.run(["printf", "%s", user_input], shell=False, check=True)
