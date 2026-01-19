import numpy as np
from pathlib import Path

from Codebase.Collection.Waveform.make_pulse_iq import make_pulse_iq
from Codebase.FileIO.collect_all_data import load_signal_grid
from Codebase.FileIO.load_hackrf_iq import load_hackrf_iq

from Codebase.Object.metadata_object import MetaDataObj
from Codebase.PeakDetection.Type1.detect_peaks_in_iq import detect_peaks_in_iq
from Codebase.Plot.plot_amplitude_freq import plot_amplitude_freq
from Codebase.Plot.plot_amplitude_time import plot_amplitude_time
from Codebase.Plot.plot_freq_time_headmap import plot_freq_time_heatmap
from Codebase.TOF.Type3.compute_relative_tof import compute_relative_tof
from Codebase.TOF.Type4.compute_tof import compute_tof
from Codebase.process_signal import process_signal
from Codebase.Filter.filter_singal import filter_signal



def run():
    metadata = MetaDataObj()

    # make_pulse_iq()

    data_dir = Path(__file__).resolve().parents[1] / "Data"
    signal_grid = load_signal_grid(data_dir)
    data_path = "/home/kevin/PycharmProjects/TVWS/Data/Collection_2026-01-11T00-41-57_15974_5188/run_0001/rx1.iq"
    iq = load_hackrf_iq(data_path)
    iq = filter_signal(metadata, iq)


    plot_freq_time_heatmap(metadata, iq)
    plot_amplitude_freq(metadata, iq)
    plot_amplitude_time(metadata, iq)



    #
    #
    # wired_signal = signal_grid[-1][0]  # same wired reference for all
    # compute_tof(metadata, wired_signal)  # do once
    # detect_peaks_in_iq(metadata,iq,"peakdetect",qty_peaks_expected)
    #
    # for row in signal_grid:
    #     for signal in row:
    #         if signal is None:
    #             continue
    #
    #         # Optional: skip processing wired against itself (remove if you want it included)
    #         if signal is wired_signal:
    #             continue
    #         detect_peaks_in_iq(metadata, signal)
    #         compute_tof(metadata, signal)
    #         process_signal(metadata, signal, wired_signal)
    #         tof_per_ft = signal.tof_air/signal.distance
    #         #print(f"Signal TOF per Foot({signal.distance:.2f}FT)= {tof_per_ft} NS")
    #
    # compute_relative_tof(metadata, signal_grid)
    # for ft, ns in metadata.average_relative_tof:
    #     ft_str = f"{int(round(ft))}" if np.isfinite(ft) else "?"
    #     ns_str = "N/A" if not np.isfinite(ns) else f"{int(round(ns)):,}"
    #     print(f"{ft_str} Ft, {ns_str} PS Per Ft Over Air")

    #metadata = MetaDataObj()
    #iq = load_hackrf_iq(metadata.selected_iq_path)
    #filtered_iq = filter_singal(metadata, iq)
    #p#lot_freq_time_heatmap(metadata, filtered_iq)
    #plot_amplitude_time(metadata, filtered_iq)
    #plot_amplitude_freq(metadata, wired_signal)

    #detect_peaks_in_iq(metadata, filtered_iq)


    #wired_iq = load_hackrf_iq(metadata.wired_iq_file_path)

if __name__ == "__main__":
    run()
