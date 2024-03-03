import os
import git
import sys

## Boilerplate to allow relative imports to work out of the box
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.dont_write_bytecode = True # Prevents pycache

from Engines.modules.tide import IndexTide

# We perform a reconciliation routine module wide to ensure that if there is 
# a staging index available, it gets merged to the cache
print("RECONCILING INDEX")
IndexTide()._cache_index(reconcile_staging=True)