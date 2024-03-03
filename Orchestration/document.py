import sys
import git
from datetime import datetime

toolchain_start_time = datetime.now()

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logging import tidemec_intro, Colors

# This trick caches a special version of the index which will seek
# and reconcile the staging index for MDRs which are in a Merge Request
from Engines.documentation import (
    mdr,
    lookups,
    mdrv2,
    metaschemas,
    models,
    vocabularies,
    wiki_navigation,
    wiki_sidebar,
)

print(tidemec_intro())

vortex = rf"""
{Colors.ORANGE}
  _   ______  ___  ___________  __  
 | | / / __ \/ _ \/_  __/ __/ |/_/  
 | |/ / /_/ / , _/ / / / _/_>  <    
 |___/\____/_/|_| /_/ /___/_/|_|    
{Colors.BLUE}{Colors.ITALICS}{Colors.BOLD}TIDeMEC Documentation Orchestration                                    
{Colors.STOP}
"""

vocabularies.run()
metaschemas.run()
lookups.run()
models.run()
mdr.run()
mdrv2.run()
wiki_navigation.run()
wiki_sidebar.run()

print("\n" + "Execution Report".center(80, "="))

time_to_execute = datetime.now() - toolchain_start_time
time_to_execute = "%.2f" % time_to_execute.total_seconds() + "seconds"

print(f"🏆 Successfully built TIDeMEC Knowledge Base in", time_to_execute)
