"""Pre-commit entry point: sync the hook's isolated env with requirements.txt, then run unittest"""

import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
sys.exit(subprocess.call([sys.executable, "-m", "unittest", "discover"]))
