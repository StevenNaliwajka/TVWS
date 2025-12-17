from Codebase.Analysis.plot_amplitude_freq import plot_amplitude_freq
from Codebase.Analysis.plot_amplitude_time import plot_amplitude_time
from Codebase.Analysis.plot_freq_time_headmap import plot_freq_time_heatmap
from Codebase.Calculations.detect_peaks_in_iq import detect_peaks_in_iq
from Codebase.FileIO.load_hackrf_iq import load_hackrf_iq

from Codebase.Filter.filter_singal import filter_singal
from Codebase.MetaData.metadata_object import MetaDataObj

def run():
    metadata = MetaDataObj()
    iq = load_hackrf_iq(metadata.wired_iq_file_path)

    filtered_iq = filter_singal(metadata, iq)
    plot_freq_time_heatmap(metadata, filtered_iq)
    plot_amplitude_time(metadata, filtered_iq)
    plot_amplitude_freq(metadata, filtered_iq)

    detect_peaks_in_iq(metadata, filtered_iq)

if __name__ == "__main__":
    run()
