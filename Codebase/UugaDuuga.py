import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
from scipy.signal import butter, filtfilt, spectrogram, find_peaks
from Codebase.FileIO.collect_all_data import load_signal_grid

from Codebase.Object.metadata_object import MetaDataObj
from Codebase.TOF.Type3.compute_relative_tof import compute_relative_tof
from Codebase.TOF.Type4.compute_tof import compute_tof
from Codebase.process_signal import process_signal


'''
Current Wants:
    add file explorer functionality to remove need for copying file name
    research possible filtering techniques to improve edge detection
    make it iterable over entire data folder
    add excel output file that tracks ToF to specified folder of certain transmission distances
    automate the magnitude and cluster distance variables
    Get some sleep
'''
def Uuga():
    # HackRF sample rate(20 MHz)
    fs = 20e6

    # Center frequency(MHz for reference)
    fc = 491e6

    metadata = MetaDataObj()
    data_dir = Path(__file__).resolve().parents[1] / "Data"
    data_dir1 = data_dir / "10 Feet" / "20251119_23-24-44_1763612684_rx2_10ft14030_tx044.iq"
    signal_grid = load_signal_grid(data_dir)

    with open(data_dir1,'r') as fid:
        raw_data = np.fromfile(fid, dtype=np.int8)

    I = raw_data[0::2]

    # MATLAB: raw_data(2:2:end)
    Q = raw_data[1::2]

    # MATLAB: complex(double(I), double(Q))
    IQ_data = I.astype(np.float64) + 1j * Q.astype(np.float64)

    # MATLAB: IQ_data = IQ_data - mean(IQ_data)
    IQ_data = IQ_data - np.mean(IQ_data)

    # MATLAB: tt = (1:length(IQ_data))/20
    tt = np.arange(1, len(IQ_data) + 1) / 20.0

    # MATLAB: wn = [0.005, 0.3];  % normalized (0..1), where 1 = Nyquist
    wn = [0.005, 0.3]

    # MATLAB: [b, a] = butter(4, wn, 'bandpass');
    b, a = butter(N=4, Wn=wn, btype='bandpass')

    # MATLAB: X = IQ_data;
    X = IQ_data.copy()

    # MATLAB: IQ_data = filtfilt(b, a, IQ_data);
    IQ_data = filtfilt(b, a, IQ_data)

    # MATLAB: phase = (unwrap(angle(X)));
    phase = np.unwrap(np.angle(X))

    # MATLAB: pshift = diff(phase)* (fs/(2*pi*1e6))+520;
    pshift = np.diff(phase) * (fs / (2 * np.pi * 1e6)) + 520

    # MATLAB: phase = phase * (fs/2*pi);
    # IMPORTANT: MATLAB left-to-right means (phase * fs / 2) * pi
    phase = phase * (fs / 2) * np.pi

    # FFT and frequency axis
    Z = np.fft.fftshift(np.fft.fft(IQ_data))

    freqs = np.linspace(-fs / 2, fs / 2, len(IQ_data))

    # Magnitude (in dB)
    mag = np.abs(IQ_data)
    mag = 20 * np.log10(mag)  # NOTE: MATLAB log() = natural log, but dB should be log10

    N = len(IQ_data)
    elapsed_sec = np.arange(N) / fs

    # Compute spectrogram

    f, t, Sxx = spectrogram(
        IQ_data,
        fs=fs,
        window='hann',
        nperseg=1024,
        noverlap=1023,
        nfft=1024,
        return_onesided=False,
        mode='magnitude'
    )

    # Center frequencies (equivalent to 'centered')
    Sxx = np.fft.fftshift(Sxx, axes=0)
    f = np.fft.fftshift(f)

    # Plot (equivalent to subplot(1,2,1))

    '''
           plt.figure()
       plt.subplot(1, 2, 1)

       plt.pcolormesh(t, f / 1e6, 20 * np.log10(Sxx + 1e-12), shading='auto')
       plt.ylabel("Frequency (MHz)")
       plt.xlabel("Time (s)")
       plt.title("Spectrogram")
       plt.colorbar(label="Magnitude (dB)")
       plt.show()

       '''
    # y-data
    minimumMag = 10

    # MATLAB: [peaks, locs] = findpeaks(abs(IQ_data), tt, 'MinPeakHeight', minimumMag);
    mag = np.abs(IQ_data)

    # SciPy find_peaks returns indices, not x-values.
    idx, props = find_peaks(mag, height=minimumMag)

    peaks = mag[idx]  # peak magnitudes (like MATLAB "peaks")
    locs = tt[idx]  # peak locations in time (like MATLAB "locs" when tt passed)

    cutoff_time = 50  # <-- choose based on your plot units
    valid = locs > cutoff_time
    locs = locs[valid]
    peaks = peaks[valid]

    # -----------------------
    # Cluster Parameters
    cluster = 7
    clusterCount = 0

    clusterPeaksArray = []
    clusterLocsArray = []

    clusterWeedOutDist = 3.5

    endDat = len(locs) - 1

    startDel = 0
    endDel = 0
    Pos = 0

    timeFilter = 350

    curLocsArray = []
    averageTimes = []
    forPos = 0
    tPos = 0

    endDat = len(locs) - 1

    clusterCount = 0
    Pos = 0  # Python 0-based

    clusterPeaksArray = []
    clusterLocsArray = []

    startDel = 0
    endDel = 0

    # -------------------------
    # First pass: collect clustered peaks/locs
    # MATLAB: for s = 1:endDat
    s = 0
    endDat = len(locs) - 1

    while s < endDat:

        # check if this could be the start of a cluster
        if (locs[s + 1] - locs[s]) < clusterWeedOutDist:
            startDel = s

            # count how long the cluster continues
            clusterCount = 0
            c = s
            while c < endDat and (locs[c + 1] - locs[c]) < clusterWeedOutDist:
                clusterCount += 1
                c += 1

            # if cluster is large enough, collect it ONCE
            if clusterCount >= cluster:
                endDel = startDel + clusterCount

                for k in range(startDel, endDel + 1):
                    if k >= len(locs):
                        break
                    if locs[k] > timeFilter:
                        break

                    clusterLocsArray.append(locs[k])
                    clusterPeaksArray.append(peaks[k])

                # 🔑 CRITICAL LINE: skip past this cluster
                s = endDel + 1
                continue

        s += 1

    # Convert to numpy arrays if you want MATLAB-like arrays
    clusterPeaksArray = np.array(clusterPeaksArray)
    clusterLocsArray = np.array(clusterLocsArray)

    # -------------------------
    # Second pass: compute average time per cluster group
    firstPoint = 0
    timeBetweenClusters = 50

    curLocsArray = []
    averageTimes = []

    # MATLAB: for s = 1:length(clusterLocsArray)-1
    for s in range(0, len(clusterLocsArray) - 1):

        # Detect a gap -> end of a cluster group
        if (clusterLocsArray[s + 1] - clusterLocsArray[s]) > timeBetweenClusters:
            endPoint = s - 1

            # Collect locs in this cluster group
            curLocsArray = []
            for c in range(firstPoint, endPoint + 1):
                curLocsArray.append(clusterLocsArray[c])

            # Average time for this group
            avgTime = np.mean(curLocsArray) if len(curLocsArray) > 0 else np.nan
            averageTimes.append(avgTime)

            # Reset for next group
            firstPoint = s

    if len(clusterLocsArray) > 0 and firstPoint < len(clusterLocsArray):
        cur = clusterLocsArray[firstPoint:]
        averageTimes = np.append(averageTimes, np.mean(cur))

    averageTimes = np.array(averageTimes)

    s = 0
    curCount = 0
    ToFArrayLocation = 0
    endDataCluster = len(clusterLocsArray) - 1
    ToFpeaksArray = np.zeros(8)
    ToFtimesArray = np.zeros(8)

    for s in range(0, endDataCluster):

        if clusterLocsArray[s + 1] - clusterLocsArray[s] > 5:
            ToFpeaksArray[ToFArrayLocation] = clusterPeaksArray[s - curCount]
            ToFpeaksArray[ToFArrayLocation + 1] = clusterPeaksArray[s]

            ToFtimesArray[ToFArrayLocation] = clusterLocsArray[s - curCount]
            ToFtimesArray[ToFArrayLocation + 1] = clusterLocsArray[s]

            curCount = -1
            ToFArrayLocation += 2
        elif s == endDataCluster - 1:
            ToFpeaksArray[ToFArrayLocation] = clusterPeaksArray[s - curCount]
            ToFpeaksArray[ToFArrayLocation + 1] = clusterPeaksArray[s + 1]

            ToFtimesArray[ToFArrayLocation] = clusterLocsArray[s - curCount]
            ToFtimesArray[ToFArrayLocation + 1] = clusterLocsArray[s + 1]

        curCount += 1

    CalcToFArray = np.zeros(4)
    s = 0
    curCount = 0
    while s < len(ToFtimesArray) - 1:
        CalcToFArray[curCount] = ToFtimesArray[s+1] - ToFtimesArray[s]
        s += 2
        curCount += 1

    for s in range(0, len(CalcToFArray)):
        print("The time of flight for signal", s + 1 ,"is", CalcToFArray[s])

    CATCHERdebug = 0

    # plt.subplot(1, 2, 1)

    # Main signals
    plt.plot(tt, np.abs(IQ_data), label="Magnitude")
    plt.plot(tt, np.imag(IQ_data), label="Imaginary")

    # Overlay clustered peaks
    plt.plot(
        clusterLocsArray,
        clusterPeaksArray,
        'ro',
        markersize=8,
        linewidth=1.5,
        label="Detected Peaks"
    )

    plt.plot(
        ToFtimesArray,
        ToFpeaksArray,
        'bo',
        markersize=8,
        linewidth=1.5,
        label="Im edging Peaks"
    )

    # Labels and title
    plt.xlabel("Time")
    plt.ylabel("Magnitude")
    plt.title("RX2 (Wireless): D=10ft")

    # Legend
    plt.legend()

    # Grid (MATLAB: grid minor)
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.minorticks_on()
    plt.show()

if __name__ == "__main__":
    Uuga()