from Codebase.Filter.filter_singal import filter_signal
from Codebase.Processing.compute_tof import compute_tof

from Codebase.Processing.compute_tof_difference import compute_tof_difference


def process_signal(metadata, signal, wired_signal):

    signal.iq = filter_signal(metadata, signal.iq)
    compute_tof(metadata, signal)
    a = metadata.a
    b = metadata.b
    c = metadata.c
    d = metadata.d
    print(f"Wired signal tof = {wired_signal.tof}")
    print(f"Signal tof = {signal.tof}")
    signal.tof_air = compute_tof_difference(wired_signal.tof, signal.tof, a, b, c, d)
