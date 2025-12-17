## takes in ,
## applies:
## Codebase/Signal/Filter/Types/bandpass_filter.py
## Codebase/Signal/Filter/Types/lower_filter.py
## Codebase/Signal/Filter/Types/upper_filter.py
from Codebase.Analysis.plot_amplitude_freq import plot_amplitude_freq
from Codebase.Analysis.plot_amplitude_time import plot_amplitude_time
from Codebase.Analysis.plot_freq_time_headmap import plot_freq_time_heatmap
from Codebase.Filter.Types.bandpass_filter import bandpass_filter
from Codebase.Filter.Types.lower_filter import lower_filter
from Codebase.Filter.Types.upper_filter import upper_filter


def filter_singal(metadata, iq):

    ## Banpass filter
    iq = bandpass_filter(metadata, iq)
    #plot_freq_time_heatmap(metadata, iq)
    #plot_amplitude_time(metadata, iq)
    plot_amplitude_freq(metadata, iq)

    ## Lower filter
    iq = lower_filter(metadata, iq)
    #plot_freq_time_heatmap(metadata, iq)
    #plot_amplitude_time(metadata, iq)
    plot_amplitude_freq(metadata, iq)

    ## Upper filter
    iq = upper_filter(metadata, iq)
    #plot_freq_time_heatmap(metadata, iq)
    #plot_amplitude_time(metadata, iq)
    plot_amplitude_freq(metadata, iq)
