# HL-TVWS

Computes TOF from our experiments.

Processes signal based off values in:
Codebase/Codebase/metadata.json


Performs 3 filters on the signal in series and displays the results of each as they work.
- Banpass Filter
- Lowpass Filter
- Upper Filter


## RUNNING - WINDOWS:
- Double click "setup.bat" to setup the project
  - This will create "Data/","Config/", and prepare ".venv"
- "Data/" folder should be populated with data.
  - No smart logic built into data processing yet.
- 
- Update "Codebase/MetaData/metadata_object.py"
  - 