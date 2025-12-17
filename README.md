# HL-TVWS

Computes TOF from our experiments.

Processes signal based off values in:
Config/metadata.json


Performs 3 filters on the signal in series.
- Banpass Filter
- Lowpass Filter
- Upper Filter


## RUNNING - WINDOWS:
- Double click "setup.bat" to setup the project
  - This will create "Data/","Config/", and prepare ".venv"
- "Data/" folder must be populated with data.
  - No smart logic built into data processing yet.

- Update "Config/metadata.json"

- Can be run by clicking on "run.bat"