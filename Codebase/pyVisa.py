import pyvisa
import numpy as np
import math

ip = "169.254.58.191"

rm = pyvisa.ResourceManager()
inst = rm.open_resource(f"TCPIP0::{ip}::inst0::INSTR")
inst.timeout = 20000
inst.write_termination = '\n'
inst.read_termination = '\n'

with open(r"C:\Users\steve\Downloads\exg_10MHz_approx30pct_iq.bin", "rb") as f:
    raw = np.frombuffer(f.read(), dtype=">i2")  # big-endian int16

inst.write("*CLS")
inst.write(":RAD:ARB:STAT OFF")

inst.write_binary_values(
    'MMEM:DATA "WFM1:TESTWFM",',
    raw,
    datatype='h',
    is_big_endian=True
)

print(inst.query('MMEM:CAT? "WFM1"'))
print(inst.query("SYST:ERR?"))

def build_pulse_iq(
    arb_fs_hz: float,
    pulse_rep_hz: float,
    duty_cycle: float,
    periods: int = 80,
    amplitude: int = 32767,
):
    """
    Build interleaved int16 IQ waveform for Keysight EXG ARB.

    Parameters
    ----------
    arb_fs_hz : float
        ARB sample rate in Sa/s. Must be <= instrument limit.
    pulse_rep_hz : float
        Desired pulse repetition frequency in Hz.
    duty_cycle : float
        Duty cycle from 0.0 to 1.0.
    periods : int
        Number of waveform periods to store. Total IQ samples must be >= 512
        and a multiple of 8 for EXG compatibility.
    amplitude : int
        Int16 amplitude for ON state.

    Returns
    -------
    iq_interleaved : np.ndarray
        Interleaved I,Q,I,Q... int16 waveform.
    samples_per_period : int
        Integer samples per repetition period.
    actual_pulse_rep_hz : float
        Actual achieved repetition frequency.
    actual_duty_cycle : float
        Actual achieved duty cycle.
    total_iq_samples : int
        Number of IQ sample pairs.
    """
    if not (0.0 < duty_cycle < 1.0):
        raise ValueError("duty_cycle must be between 0 and 1.")
    if amplitude < 0 or amplitude > 32767:
        raise ValueError("amplitude must be in [0, 32767].")

    # Integer samples per period required for repeating digital waveform
    samples_per_period = int(round(arb_fs_hz / pulse_rep_hz))
    if samples_per_period < 1:
        raise ValueError("samples_per_period became < 1. Lower pulse_rep_hz or raise arb_fs_hz.")

    actual_pulse_rep_hz = arb_fs_hz / samples_per_period

    on_samples = max(1, min(samples_per_period - 1, int(round(duty_cycle * samples_per_period))))
    actual_duty_cycle = on_samples / samples_per_period

    # Build one period: ON then OFF
    one_period_i = np.zeros(samples_per_period, dtype=np.int16)
    one_period_i[:on_samples] = amplitude
    one_period_q = np.zeros(samples_per_period, dtype=np.int16)

    # Repeat
    I = np.tile(one_period_i, periods)
    Q = np.tile(one_period_q, periods)

    total_iq_samples = len(I)

    # Enforce EXG-friendly length: >=512 and multiple of 8 IQ samples
    if total_iq_samples < 512:
        extra_periods = math.ceil((512 - total_iq_samples) / samples_per_period)
        I = np.tile(one_period_i, periods + extra_periods)
        Q = np.tile(one_period_q, periods + extra_periods)
        total_iq_samples = len(I)

    remainder = total_iq_samples % 8
    if remainder != 0:
        needed = 8 - remainder
        I = np.concatenate([I, one_period_i[:needed]])
        Q = np.concatenate([Q, one_period_q[:needed]])
        total_iq_samples = len(I)

    # Interleave IQ: I0,Q0,I1,Q1,...
    iq_interleaved = np.empty(total_iq_samples * 2, dtype=np.int16)
    iq_interleaved[0::2] = I
    iq_interleaved[1::2] = Q

    return iq_interleaved, samples_per_period, actual_pulse_rep_hz, actual_duty_cycle, total_iq_samples


def connect_exg(ip_address: str):
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(f"TCPIP0::{ip_address}::inst0::INSTR")
    inst.timeout = 20000
    inst.write_termination = "\n"
    inst.read_termination = "\n"
    return rm, inst


def upload_waveform_to_wfm1(inst, waveform_name: str, iq_interleaved: np.ndarray):
    """
    Upload waveform directly into WFM1 memory.
    """
    inst.write("*CLS")
    inst.write(":RAD:ARB:STAT OFF")

    # Send interleaved int16 IQ data as binary block
    inst.write_binary_values(
        f'MMEM:DATA "WFM1:{waveform_name}",',
        iq_interleaved,
        datatype="h",
        is_big_endian=True,
    )

    print("Upload error status:", inst.query("SYST:ERR?"))
    print("WFM1 catalog:", inst.query('MMEM:CAT? "WFM1"'))


def configure_and_run(
    inst,
    waveform_name: str,
    arb_fs_hz: float,
    rf_freq_hz: float,
    rf_power_dbm: float,
):
    """
    Select waveform, set sample rate, RF frequency/power, and turn output on.
    """
    inst.write(f':RAD:ARB:WAV "WFM1:{waveform_name}"')
    inst.write(f":RAD:ARB:SCL:RATE {arb_fs_hz}")
    inst.write(":RAD:ARB:STAT ON")
    inst.write(f":FREQ {rf_freq_hz}")
    inst.write(f":POW {rf_power_dbm}")
    inst.write(":OUTP ON")

    print("Selected waveform, ARB, RF:")
    print("  ARB state:", inst.query(":RAD:ARB:STAT?").strip())
    print("  RF output:", inst.query(":OUTP?").strip())
    print("  Error:", inst.query("SYST:ERR?").strip())


if __name__ == "__main__":
    # =========================
    # USER-TUNABLE PARAMETERS
    # =========================
    EXG_IP = "169.254.58.191"

    WAVEFORM_NAME = "PULSE10M"
    ARB_FS_HZ = 70e6          # 70 MSa/s
    PULSE_REP_HZ = 10e3       # target repetition frequency
    DUTY_CYCLE = 0.50         # desired duty cycle
    PERIODS = 20            # waveform length in periods
    AMPLITUDE = 18000        # full-scale ON amplitude

    RF_FREQ_HZ = 915e6        # RF carrier
    RF_POWER_DBM = -10        # output power

    # =========================
    # BUILD WAVEFORM
    # =========================
    iq, spp, actual_prf, actual_duty, total_iq = build_pulse_iq(
        arb_fs_hz=ARB_FS_HZ,
        pulse_rep_hz=PULSE_REP_HZ,
        duty_cycle=DUTY_CYCLE,
        periods=PERIODS,
        amplitude=AMPLITUDE,
    )

    print("Waveform summary:")
    print(f"  Requested PRF:      {PULSE_REP_HZ:.6f} Hz")
    print(f"  Actual PRF:         {actual_prf:.6f} Hz")
    print(f"  Requested duty:     {DUTY_CYCLE * 100:.4f} %")
    print(f"  Actual duty:        {actual_duty * 100:.4f} %")
    print(f"  Samples/period:     {spp}")
    print(f"  Total IQ samples:   {total_iq}")
    print(f"  Interleaved points: {len(iq)}")

    # =========================
    # CONNECT / UPLOAD / RUN
    # =========================
    rm, inst = connect_exg(EXG_IP)

    try:
        print("IDN:", inst.query("*IDN?").strip())

        upload_waveform_to_wfm1(inst, WAVEFORM_NAME, iq)

        configure_and_run(
            inst,
            waveform_name=WAVEFORM_NAME,
            arb_fs_hz=ARB_FS_HZ,
            rf_freq_hz=RF_FREQ_HZ,
            rf_power_dbm=RF_POWER_DBM,
        )

    finally:
        inst.close()
        rm.close()