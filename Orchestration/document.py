import sys
import git
from datetime import datetime

toolchain_start_time = datetime.now()

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import coretide_intro, ANSI

# This trick caches a special version of the index which will seek
# and reconcile the staging index for MDRs which are in a Merge Request
from Engines.documentation import (
    mdr,
    lookups,
    metaschemas,
    models,
    vocabularies,
    wiki_navigation,
    wiki_sidebar,
)

print(coretide_intro())

vortex = rf"""
{ANSI.Colors.ORANGE}
  _   ______  ___  ___________  __  
 | | / / __ \/ _ \/_  __/ __/ |/_/  
 | |/ / /_/ / , _/ / / / _/_>  <    
 |___/\____/_/|_| /_/ /___/_/|_|    
{ANSI.Colors.BLUE}{ANSI.Formatting.ITALICS}{ANSI.Formatting.BOLD}CoreTIDE Documentation Orchestration                                    
{ANSI.Formatting.STOP}
"""

vocabularies.run()
metaschemas.run()
lookups.run()
models.run()
mdr.run()
wiki_navigation.run()
wiki_sidebar.run()