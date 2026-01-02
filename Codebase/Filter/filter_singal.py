## takes in ,
## applies:
## Codebase/Signal/Filter/Types/bandpass_filter.py
## Codebase/Signal/Filter/Types/lower_filter.py
## Codebase/Signal/Filter/Types/upper_filter.py

from Codebase.Filter.Types.bandpass_filter import bandpass_filter
from Codebase.Filter.Types.lower_filter import lower_filter
from Codebase.Filter.Types.upper_filter import upper_filter
from Codebase.Plot.plot_amplitude_freq import plot_amplitude_freq
from Codebase.Plot.plot_amplitude_time import plot_amplitude_time
from Codebase.Plot.plot_freq_time_headmap import plot_freq_time_heatmap


def filter_signal(metadata, iq):

    ## Banpass filter
    #plot_freq_time_heatmap(metadata, iq)
    #plot_amplitude_time(metadata, iq)
    #plot_amplitude_freq(metadata, iq)
    #plot_amplitude_freq(metadata, iq)
    iq = bandpass_filter(metadata, iq)
    #plot_amplitude_freq(metadata, iq)

    #plot_freq_time_heatmap(metadata, iq)
    #plot_amplitude_time(metadata, iq)

    ## Lower filter
    #plot_amplitude_freq(metadata, iq)
    iq = lower_filter(metadata, iq)
    #plot_amplitude_freq(metadata, iq)
    #plot_freq_time_heatmap(metadata, iq)
    #plot_amplitude_time(metadata, iq)

    ## Upper filter
    #plot_amplitude_freq(metadata, iq)
    iq = upper_filter(metadata, iq)
    #plot_freq_time_heatmap(metadata, iq)
    #plot_amplitude_time(metadata, iq)
    #plot_amplitude_freq(metadata, iq)
    return iq