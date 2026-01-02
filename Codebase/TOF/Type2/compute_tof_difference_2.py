def compute_tof_difference_2(signal, wired_signal):
    tof_air = signal.tof - wired_signal.tof
    return tof_air