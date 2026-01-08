#!/usr/bin/env bash
set -euo pipefail

# ---- Config ----
FREQ=520000000           # center frequency (Hz)
SR=20000000              # sample rate (Hz)
NSAMPLES=10000000        # number of samples to capture
AMP=28                 # TX amplitude/gain (for hackrf_transfer -x)
PASS='Kennesaw123'       # password for both remote Pis (you provided)
RX1_USER=pi1; RX1_HOST=100.101.107.104
RX2_USER=pi2; RX2_HOST=100.85.78.54
LOCAL_SAVE_DIR="$HOME/sdr"

#mkdir -p "$LOCAL_SAVE_DIR"

# ---- Function: arm a receiver (2 args only) ----
#arm_rx() {
#  local user=$1 host=$2
#  echo "[$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)] Arming receiver $user@$host ..."
  # Use sshpass to send an ssh command that runs hackrf_transfer in background,
  # waiting for the hardware trigger (--trig).
#  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$user@$host" \
#    "nohup hackrf_transfer -r capture_tmp.iq -f $FREQ -s $SR -n $NSAMPLES -H echo \$! > /tmp/hackrf_pid.txt"
#}

# ---- Arm both receivers ----
#sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$RX1_USER@$RX1_HOST" \
#    "nohup bash /opt/sdr/rx1.sh"
    
#sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$RX2_USER@$RX2_HOST" \
#    "nohup bash /opt/sdr/rx2.sh"

# start both arm scripts concurrently and keep their stdout locally
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$RX1_USER@$RX1_HOST" \
  "hackrf_transfer -r capture_1.iq -n 25000 -f 520000000 -s 20000000 -l 16 -g 16 -H" > rx1.log 2>&1 &
PID1=$!

sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$RX2_USER@$RX2_HOST" \
  "hackrf_transfer -r capture_2.iq -n 25000 -f 520000000 -s 20000000 -l 16 -g 16 -H" > rx2.log 2>&1 &
PID2=$!
sleep 0.25
# (optional) wait until both scripts print a READY line before firing the trigger
# e.g., have rx?.sh echo "ARMED" after GPIO is set up and waiting on the edge.
#grep -q "ARMED" <(tail -n +1 -f rx1.log) & W1=$!
#grep -q "ARMED" <(tail -n +1 -f rx2.log) & W2=$!
#wait $W1; wait $W2

# ---- Record TX timestamp and trigger TX ----
timestamp=$(date -u +%Y-%m-%dT%H-%M-%S_%4N)
echo "[$timestamp] Triggering TX locally..."

# Transmit and cause hardware trigger to fire on the TX device
# Use --trig-tx so that connected RXs waiting on their trig lines get the event.
hackrf_transfer -t pulse.iq -f $FREQ -s $SR -x $AMP

# wait for both to finish, then continue (scp, delete, process…)
#wait $PID1
#wait $PID2



# ---- Wait for remote captures to complete ----
# Compute capture duration (in seconds) and sleep a bit longer to ensure remote writes finish
capture_secs=$(awk "BEGIN {printf \"%f\", $NSAMPLES/$SR}")
safety_margin=1.0    # seconds (extra time to allow for USB/host flush)
sleep_time=$(awk "BEGIN {printf \"%f\", $capture_secs + $safety_margin}")
echo "Waiting ${sleep_time}s for remote captures to finish..."
sleep "$sleep_time"

# ---- Rename remote capture files with TX timestamp ----
#echo "Renaming remote capture files to include timestamp ${timestamp} ..."
#sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$RX1_USER@$RX1_HOST" \
#  "mv -f capture_1.iq ${timestamp}_1.iq || echo 'RX1: capture_tmp.iq not found'"
#sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$RX2_USER@$RX2_HOST" \
#  "mv -f capture_2.iq ${timestamp}_2.iq || echo 'RX2: capture_tmp.iq not found'"

# ---- Retrieve files to local machine ----
echo "Copying files to local machine ($LOCAL_SAVE_DIR)..."
sleep 1
sshpass -p "$PASS" scp -o StrictHostKeyChecking=no "$RX1_USER@$RX1_HOST:home/pi1/capture_1.iq" \
  "$LOCAL_SAVE_DIR" || echo "Failed to copy rx1" &
sshpass -p "$PASS" scp -o StrictHostKeyChecking=no "$RX2_USER@$RX2_HOST:home/pi2/capture_2.iq" \
  "$LOCAL_SAVE_DIR" || echo "Failed to copy rx2"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S.%4N)] All done. Files saved:"
echo "  $LOCAL_SAVE_DIR/capture_1.iq"
echo "  $LOCAL_SAVE_DIR/capture_2.iq"

