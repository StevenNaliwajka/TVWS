%clear

% Define file name and parameters
data_dir = 'C:\Users\steve\PycharmProjects\TVWS\Data\0';
filename = fullfile(data_dir, '2026-01-05T02-06-33_1596_capture_1.iq');  % Full path to the IQ capture
fs = 20e6;  % HackRF sample rate (20 MHz)
fc = 491e6;  % Center frequency (MHz for reference)

% Open and read file
if exist(filename, 'file') ~= 2
    error('IQ file not found: %s', filename);
end

fid = fopen(filename, 'rb');
if fid < 0
    error('Failed to open IQ file: %s', filename);
end

raw_data = fread(fid, 'int8');
fclose(fid);

% --- Extract timestamp from filename ---
%[~, name, ~] = fileparts(filename);
%tokens = regexp(name, '(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-(\d{2})_(\d{4})', 'tokens');
%if isempty(tokens)
%    error('Filename does not contain a valid timestamp.');
%end
%parts = tokens{1};
%date_str = sprintf('%s-%s-%s', parts{1}, parts{2}, parts{3});
%time_str = sprintf('%s:%s:%s.%s', parts{4}, parts{5}, parts{6}, parts{7});
%start_time = datetime([date_str, ' ', time_str], 'InputFormat', 'yyyy-MM-dd HH:mm:ss.SSS');

% Separate I and Q components
I = raw_data(1:2:end);
Q = raw_data(2:2:end);
IQ_data = complex(double(I), double(Q));
IQ_data = IQ_data - mean(IQ_data);  % DC offset removal
tt = 1:length(IQ_data);
% --- Bandpass Filter Design ---
%f_low = 488e6;  % Lower edge of passband
%f_high = 494e6; % Upper edge of passband
%f_nyq = fs / 2;
wn = [0.15, 0.3];  % Normalized frequencies (0 to 1)
[b, a] = butter(4, wn, 'bandpass');  % 4th-order Butterworth filter
X = IQ_data;

IQ_data = filtfilt(b, a, IQ_data);
phase =(unwrap(angle(X)));
pshift = diff(phase)* (fs/(2*pi*1e6))+520;
phase = phase * (fs/2*pi);

Z = fftshift(fft(IQ_data));
freqs = linspace(-fs/2, fs/2, length(IQ_data));
mag = abs(IQ_data);
mag = 20*log(mag);
% Time axis
N = length(IQ_data);
elapsed_sec = seconds((0:N-1) / fs);
%time_axis = start_time + elapsed_sec;

% Plot filtered magnitude
figure;
subplot(1,2,1);
%yyaxis right
%plot(time_axis, abs(IQ_data));
%plot(tt, phase);
%yyaxis left
%plot(tt, phase)
%xlabel('Time (us)');
%ylabel('MHz');
spectrogram(IQ_data, 1024, 1023, 1024, 20e6, 'yaxis', 'centered');
%title('LFM Chirp Phase Shift');
%legend("Instantaneous Phase", "Instantaneous Freq.")
%grid minor;
%ax = gca;
%ax.XAxis.TickLabelFormat = 'HH:mm:ss.SSSSS';

%figure;
%yyaxis left
subplot(1,2,2);
plot(tt,real(IQ_data), tt,imag(IQ_data))% real(IQ_data),tt, imag(IQ_data));
xlabel('Time)');
ylabel('Magnitude');
%title({'TVWS Signal', '(6th-Order Butterworth Stopband Filter Applied)', 'SDR 3'' West of Rx Tower (6" Below Grade)'});
title({'RX2 (Wireless): D=25ft a=0 l=32 g=32 | TX: a=1 x=44'});
legend("Magnitude", "Frequency");

grid minor;

%yyaxis right
%plot(time_axis, phase, 'r');
%ylabel('Instantaneous Phase (Degrees)')
%ax = gca;
%ax.XAxis.TickLabelFormat = 'HH:mm:ss.SSSSS';

%figure;
%plot(freqs,abs(Z));
