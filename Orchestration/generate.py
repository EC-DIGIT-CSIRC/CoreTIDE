from datetime import datetime
import git
import sys

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log, Colors, tidemec_intro
from Engines.modules.tide import IndexTide
from Engines.indexing import models_indexer, reports_indexer
from Engines.framework import templates
print(tidemec_intro())

toolchain_start_time = datetime.now()

riptide = rf"""
{Colors.ORANGE}
   ___  _______  _____________  ____  
  / _ \/  _/ _ \/_  __/  _/ _ \/ __/  
 / , _// // ___/ / / _/ // // / _/    
/_/|_/___/_/    /_/ /___/____/___/    
{Colors.BLUE}{Colors.ITALICS}{Colors.BOLD}TIDeMEC Meta Model Compilation Orchestration
{Colors.STOP}
"""

print(riptide)

log("TITLE", "TIDE Indexes Generation")
log(
    "INFO",
    "Generate entries in Tide namespace containing model data supportive of other generation routines",
)

models_indexer.run()
reports_indexer.run()
templates.run()

IndexTide.reload()
from Engines.framework import json_schemas, vscode_snippets

json_schemas.run()
vscode_snippets.run()


time_to_execute = datetime.now() - toolchain_start_time
time_to_execute = "%.2f" % time_to_execute.total_seconds() + " seconds"

log("SUCCESS", "Completed framework generation toolchain", time_to_execute)
