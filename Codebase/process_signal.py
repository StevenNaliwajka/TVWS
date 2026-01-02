from Codebase.Filter.filter_singal import filter_signal
from Codebase.TOF.Type4.compute_tof import compute_tof

from Codebase.TOF.Type2.compute_tof_difference_2 import compute_tof_difference_2


def process_signal(metadata, signal, wired_signal):

    signal.iq = filter_signal(metadata, signal.iq)
    compute_tof(metadata, signal)
    a = metadata.a
    b = metadata.b
    c = metadata.c
    d = metadata.d
    #print(f"Wired signal tof = {wired_signal.tof}")
    #print(f"Signal tof = {signal.tof}")

    ## TWO types of compute TOF.
    #1 uses wire lengths
    #2 uses relative.
    # signal.tof_air = compute_tof_difference_1(wired_signal.tof, signal.tof, a, b, c, d)
    signal.tof_air = compute_tof_difference_2(signal, wired_signal)