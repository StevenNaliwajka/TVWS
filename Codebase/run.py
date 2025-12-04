from Codebase.Plots.plot_freq_time_headmap import plot_freq_time_heatmap
from Codebase.ProcessSignal.detect_peaks_in_iq import detect_peaks_in_iq
from Codebase.ProcessSignal.load_hackrf_iq import load_hackrf_iq
from Codebase.ProcessSignal.process_iq import process_iq

# === Hard-coded configuration ===
iq_path = "/home/kevin/PycharmProjects/TVWS/data/OneDrive_1_12-2-2025/50 Feet/20251123_14-07-31_1763924851_rx2_50ft05240_tx144.iq"
FS_HZ = 4.91e8          # <-- put your actual sample rate here
TOP_N = 20            # number of strongest peaks to display
MIN_HEIGHT = None     # or e.g. 0.1 to filter out small peaks
METHOD = "peakdetect" # one of: "peakdetect", "topology", "caerus"


def run():

    plot_freq_time_heatmap(
        iq_path=iq_path,  # same file you used with hackrf_transfer
        sample_rate_hz=20e6,  # from -s 20000000
        center_freq_hz=491e6,  # from -f 491000000
        span_mhz=10.0,  # e.g. show ±10 MHz around center
    )

    # 1) Load complex IQ
    raw_iq = load_hackrf_iq(iq_path)
    iq = process_iq(raw_iq)

    ## Used to 'ignore' filter.
    #iq = raw_iq

    peaks = detect_peaks_in_iq(
        iq,
        sample_rate_hz=FS_HZ,
        method=METHOD,
        min_height=MIN_HEIGHT,
    )

    # Sort by amplitude and show top N
    peaks_sorted = peaks.sort_values("amplitude", ascending=False).head(TOP_N)
    # print(peaks_sorted[["time_ns", "amplitude"]].to_string(index=False))


if __name__ == "__main__":
    run()
