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



sudo apt install -y hackrf

bash local_collect.sh --runs 1000 --no-hw-trigger \
  --rx1-serial 0000000000000000930c64dc292c35c3 \
  --rx2-serial 000000000000000087c867dc2b54905f \
  --tx-serial  0000000000000000930c64dc2a0a66c3