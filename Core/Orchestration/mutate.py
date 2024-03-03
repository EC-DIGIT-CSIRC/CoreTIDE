import os
import git
import toml
import sys
from datetime import datetime
from pathlib import Path

toolchain_start_time = datetime.now()

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Core.Engines.modules.logging import log, Colors, tidemec_intro
from Core.Engines.mutation import (
    file_name,
    reports,
    remove_cdm_validation,
    references,
)

ROOT = Path(str(git.Repo(".", search_parent_directories=True).working_dir))

print(tidemec_intro())

maelstrom = rf"""
{Colors.ORANGE}
   __  ______   ______   _____________  ____  __  ___
  /  |/  / _ | / __/ /  / __/_  __/ _ \/ __ \/  |/  /
 / /|_/ / __ |/ _// /___\ \  / / / , _/ /_/ / /|_/ / 
/_/  /_/_/ |_/___/____/___/ /_/ /_/|_|\____/_/  /_/  
{Colors.BLUE}{Colors.ITALICS}{Colors.BOLD}TIDeMEC Data Mutation Orchestration   
{Colors.STOP}
"""

print(maelstrom)

file_name.run()
reports.run()
remove_cdm_validation.run()
references.run()


print("\n" + "Execution Report".center(80, "="))

time_to_execute = datetime.now() - toolchain_start_time
time_to_execute = "%.2f" % time_to_execute.total_seconds() + " seconds"

log("SUCCESS", "Completed mutation toolchain", time_to_execute)
