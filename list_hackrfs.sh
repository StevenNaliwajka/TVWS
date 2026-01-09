#!/usr/bin/env bash
set -euo pipefail

# list_hackrfs.sh
# Lists HackRF devices plugged into THIS machine and prints their USB location + serial.
#
# Serial numbers printed here are what HackRF host tools expect for "-d <serial>" when selecting devices.
# (HackRF docs: use -d with a serial number when multiple devices are connected.)

if ! command -v udevadm >/dev/null 2>&1; then
  echo "[list_hackrfs.sh] ERROR: udevadm not found. (On Debian/Ubuntu it's in: udev)" >&2
  exit 1
fi

# Prefer sysfs enumeration (works even if hackrf tools aren't installed)
SYSFS="/sys/bus/usb/devices"

# Collect candidate devices by product string
mapfile -t DEV_DIRS < <(
  find "$SYSFS" -maxdepth 1 -mindepth 1 -type l -print 2>/dev/null \
    | while read -r d; do
        prod_file="$d/product"
        [[ -f "$prod_file" ]] || continue
        prod="$(tr -d '\0' < "$prod_file" 2>/dev/null || true)"
        if [[ "$prod" =~ HackRF ]]; then
          echo "$d"
        fi
      done
)

# Fallback: match vendor/product IDs seen in lsusb output (useful if product string differs)
if [[ "${#DEV_DIRS[@]}" -eq 0 ]] && command -v lsusb >/dev/null 2>&1; then
  # Many HackRF One devices show up as 1d50:6089 (OpenMoko / Great Scott Gadgets).
  # We'll locate the sysfs device via /dev/bus/usb/BBB/DDD then follow to its sysfs path.
  while read -r line; do
    # Example: Bus 001 Device 004: ID 1d50:6089 OpenMoko, Inc. Great Scott Gadgets HackRF One
    bus="$(awk '{print $2}' <<<"$line")"
    dev="$(awk '{print $4}' <<<"$line" | tr -d ':')"
    node="/dev/bus/usb/${bus}/${dev}"
    [[ -e "$node" ]] || continue
    sys_path="$(udevadm info -q path -n "$node" 2>/dev/null || true)"
    [[ -n "$sys_path" ]] || continue
    # Convert /devices/... to /sys/devices/...
    sys_full="/sys${sys_path}"
    # Walk up until we find a directory that has a "product" file
    cur="$sys_full"
    for _ in {1..6}; do
      if [[ -f "$cur/product" ]]; then
        DEV_DIRS+=("$cur")
        break
      fi
      cur="$(dirname "$cur")"
    done
  done < <(lsusb | grep -iE 'hackrf|1d50:6089' || true)
fi

if [[ "${#DEV_DIRS[@]}" -eq 0 ]]; then
  echo "[list_hackrfs.sh] No HackRF devices found."
  echo "  - Check USB power/cables and run: lsusb | grep -i hackrf"
  exit 0
fi

printf "%-6s %-6s %-14s %-40s %s\n" "BUS" "DEV" "VID:PID" "SERIAL" "PRODUCT"
printf "%-6s %-6s %-14s %-40s %s\n" "----" "----" "------" "------" "-------"

# De-dup in case fallback added duplicates
declare -A seen
for d in "${DEV_DIRS[@]}"; do
  real="$(readlink -f "$d" 2>/dev/null || echo "$d")"
  [[ -n "${seen[$real]+x}" ]] && continue
  seen[$real]=1

  bus="$(cat "$real/busnum" 2>/dev/null || echo "?")"
  devnum="$(cat "$real/devnum" 2>/dev/null || echo "?")"
  vid="$(cat "$real/idVendor" 2>/dev/null || echo "????")"
  pid="$(cat "$real/idProduct" 2>/dev/null || echo "????")"
  prod="$(tr -d '\0' < "$real/product" 2>/dev/null || echo "HackRF")"

  # USB iSerial is usually available at $real/serial; udev can also provide ID_SERIAL_SHORT.
  serial=""
  if [[ -f "$real/serial" ]]; then
    serial="$(tr -d '\0' < "$real/serial" 2>/dev/null || true)"
  fi
  if [[ -z "$serial" ]]; then
    node="/dev/bus/usb/$(printf "%03d" "$bus")/$(printf "%03d" "$devnum")"
    if [[ -e "$node" ]]; then
      serial="$(udevadm info -q property -n "$node" 2>/dev/null | awk -F= '/^ID_SERIAL_SHORT=/{print $2; exit}')"
    fi
  fi
  [[ -n "$serial" ]] || serial="(no-serial)"

  printf "%-6s %-6s %-14s %-40s %s\n" \
    "$(printf "%03d" "$bus" 2>/dev/null || echo "$bus")" \
    "$(printf "%03d" "$devnum" 2>/dev/null || echo "$devnum")" \
    "${vid}:${pid}" \
    "$serial" \
    "$prod"
done

echo
echo "Tip: target a specific device with HackRF tools like:"
echo "  hackrf_transfer -d <SERIAL> ..."
