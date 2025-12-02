from Codebase.Plots.plot_freq_time_headmap import plot_freq_time_heatmap
from Codebase.detect_peaks_in_iq import detect_peaks_in_iq

# === Hard-coded configuration ===
IQ_PATH = "/home/kevin/PycharmProjects/TVWS/data/OneDrive_1_12-2-2025/15 Feet/20251119_23-29-59_1763612999_rx2_15ft14030_tx044.iq"
FS_HZ = 4.91e8          # <-- put your actual sample rate here
TOP_N = 20            # number of strongest peaks to display
MIN_HEIGHT = None     # or e.g. 0.1 to filter out small peaks
METHOD = "peakdetect" # one of: "peakdetect", "topology", "caerus"


def run():
    #
    #plot_freq_time_heatmap(
    #    iq_path=IQ_PATH,  # same file you used with hackrf_transfer
    #    sample_rate_hz=20e6,  # from -s 20000000
    #    center_freq_hz=491e6,  # from -f 491000000
    #    span_mhz=10.0,  # e.g. show ±10 MHz around center
    #)

    peaks = detect_peaks_in_iq(
        IQ_PATH,
        sample_rate_hz=FS_HZ,
        method=METHOD,
        min_height=MIN_HEIGHT,
    )

    # Sort by amplitude and show top N
    peaks_sorted = peaks.sort_values("amplitude", ascending=False).head(TOP_N)
    # print(peaks_sorted[["time_ns", "amplitude"]].to_string(index=False))


if __name__ == "__main__":
    run()
