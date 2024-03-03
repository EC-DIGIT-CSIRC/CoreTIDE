import os
import git
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log, Colors, tidemec_intro
from Engines.validation import (
    id_uniqueness,
    uuid_v4,
    schema,
    cve,
)

toolchain_start_time = datetime.now()

print(tidemec_intro())

quickstream = rf"""
{Colors.ORANGE}  
  ____  __  _____________ _______________  _______   __  ___  
 / __ \/ / / /  _/ ___/ //_/ __/_  __/ _ \/ __/ _ | /  |/  /  
/ /_/ / /_/ // // /__/ ,< _\ \  / / / , _/ _// __ |/ /|_/ /   
\___\_\____/___/\___/_/|_/___/ /_/ /_/|_/___/_/ |_/_/  /_/    
{Colors.BLUE}{Colors.ITALICS}{Colors.BOLD}TIDeMEC Object Data Validation Orchestration

{Colors.STOP}
"""

print(quickstream)

os.environ["VALIDATION_ERROR_RAISED"] = ""
os.environ["VALIDATION_WARNING_RAISED"] = ""

id_uniqueness.run()
uuid_v4.run()
schema.run()
cve.run()

print("\n" + "Execution Report".center(80, "="))

time_to_execute = datetime.now() - toolchain_start_time
time_to_execute = "%.2f" % time_to_execute.total_seconds() + " seconds"

log("INFO", "Completed validation toolchain", time_to_execute)

if os.environ.get("VALIDATION_ERROR_RAISED"):
    log(
        "WARNING",
        "Some validation scripts failed.",
        advice="Review the error logs to discover the problem",
    )
    raise Exception("Validation Failed")

if os.environ.get("VALIDATION_WARNING_RAISED"):
    sys.exit(19)
else:
    log("SUCCESS", "All content successfully passed validation")
