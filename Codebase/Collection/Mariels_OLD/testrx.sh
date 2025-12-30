#!/usr/bin/env bash
set -euo pipefail

for i in {1..5}; do
    timestamp=$(date -u +%Y-%m-%dT%H-%M-%S_%4N)
    hackrf_transfer -f 510000000 -s 20000000 -r testrx_$i.iq -a 0 -n 400 &
    PID1=$!
    wait $PID1
    #kill $PID1
done
