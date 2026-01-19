import numpy as np
"""
sr = 8_000_000; chips = np.array([1,1,1,1,1,-1,-1,1,1,-1,1,-1,1], dtype=float)
sps = sr//1_000_000                                  # 8 samples per chip
symbols = np.repeat(chips, sps).astype(np.complex64) # I=±1, Q=0
iq = 0.7*symbols
(np.vstack((iq.real, iq.imag)).T*127).astype(np.int8).ravel().tofile("pulse.iq")


#chirp
sr  = 20_000_000
dur = 0.00001
t_pad = np.arange(int(512))/sr
pad = np.zeros_like(t_pad, dtype=np.int8)

f0, f1 = -1_000_000, 2_000_000   # BASEBAND sweep
t = np.arange(int(sr*dur))/sr
phase = 2*np.pi*(f0*t + 0.5*(f1-f0)*(t**2)/dur)
iq  = 0.8*np.exp(1j*phase)
iq = np.concatenate((pad, iq))
(np.column_stack((iq.real, iq.imag))*127).astype(np.int8).ravel().tofile("pulse.iq")

"""


#single tone
sr = 20_000_000
dur = 0.0001
dur2 = 0.00001
t_pad = np.arange(int(512*2))/sr
pad = np.zeros_like(t_pad, dtype=np.int8)
f = -2_000_000
f2 = 2_000_000
t2 = np.arange(int(sr*dur2))/sr
t = np.arange(int(sr*dur2))/sr
iq = np.exp(1j*2*np.pi*f*t) * 0.9                      # 0.7 to avoid clipping
signal = np.exp(1j*2*np.pi*f2*t2) * 0.9                      # 0.7 to avoid clipping
iq = np.concatenate((signal,pad,signal,pad,signal))#,pad, iq))
iq8 = (np.vstack((iq.real, iq.imag)).T * 127).astype(np.int8).ravel()
iq8.tofile("pilot_threepulses.iq")

"""
# ---- SAWTOOTH (amplitude) -> I = sawtooth, Q = 0 ----
sr  = 8_000_000
dur = 0.002                   
f   = 100_000                 # 100 kHz fundamental
t   = np.arange(int(sr*dur))/sr

# Rising sawtooth in [-1, +1]:
saw = 2.0 * ((f*t) - np.floor(0.5 + f*t))

# Scale to avoid clipping and write interleaved int8 IQ
A   = 0.7
I   = A * saw
Q   = np.zeros_like(I)
iq8 = (np.column_stack((I, Q)) * 127).astype(np.int8).ravel()
iq8.tofile("sawpulse.iq")


# chirp_520MHz_50us_baseband_±2MHz windowed, saved as int8 IQ
import numpy as np
Fs=10_000_000; T=50e-6; B=4_000_000
t=np.arange(int(Fs*T))/Fs; k=B/T
phase=2*np.pi*(-B/2*t + 0.5*k*t**2)
w=np.hanning(len(t))
iq=0.3*w*np.exp(1j*phase)   # -40 dB digital attenuation
(np.column_stack([iq.real,iq.imag])*127).astype(np.int8).ravel().tofile('pulse.iq')
"""