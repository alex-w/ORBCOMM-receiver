##############################################################################
#
# Author: Frank Bieberly
# Date: 27 March 2019
# Name: timing_recovery.py
# Description: 
# This is a demo of transmitting and receiving qpsk samples. It uses a RRC 
# pulse shaping filter and matched filter on the receiver. Additionally,
# a timing offset has been added to the Tx samples. After matched filtering
# there is a timing recovery loop to estimate the timing offset.
#
##############################################################################

import numpy as np
import scipy.signal as scisig
import matplotlib.pyplot as plt
from utilities import gen_bits, qpsk_symbols, rrcosfilter

if __name__ == '__main__':
    num_symbols = 500
    samples_per_symbol = 4

    bits = gen_bits(num_symbols*2, zero_runs=False, one_runs=False)
    symbols = qpsk_symbols(bits, samples_per_symbol)

    # Create RRC taps
    alpha = 0.4
    baudrate = 1.
    num_of_symbols_half_filter = 4
    rrc_num_taps = samples_per_symbol * num_of_symbols_half_filter * 2.
    t_idx, rrc_taps = rrcosfilter(rrc_num_taps, alpha, baudrate, samples_per_symbol)

    # Plot the RRC taps
    plt.figure()
    plt.title("RRC taps")
    plt.plot(rrc_taps)
    plt.grid()

    # Normalize RRC filter, helps with the plotting
    rrc_taps /= np.sum(rrc_taps)

    # Pulse shape filter the tx_samples
    # Notice the rrc filter taps are multiplied by samples_per_symbol
    # This normalizes the power in the samples (after the zero stuffing)
    tx_samples = scisig.lfilter(rrc_taps[::]*samples_per_symbol, [1.0], symbols[::])

    # add timing offset here
    # interpolate pulse shape filter output
    # Play with the timing offset to see the effect on the Tx samples
    # But the Rx samples should remain tight
    dt = 0.5                                             # Timing offset
    tau = dt                                             # timing correction to be applied
    th  = np.array([-2, -1, 0, 1, 2])                    # time vector for interpolating filter
    w   = np.sqrt(np.hamming(5).T)                       # window function for interpolating filter
    hi  = np.sinc(th + tau) * w                          # interpolating filter coefficients
    hi /= np.sum(hi)                                     # normalize filter taps for plotting purposes
    tx_samples   = scisig.lfilter(hi, [1.0], tx_samples) # interpolate matched filter output

    # The interpolating filter adds a delay to the correct symbol position
    sample_delay = int((len(th)-1)/2)

    # Matched filter the samples at the receiver with same RRC filter
    mf_samples_with_offset = scisig.lfilter(rrc_taps[::], [1.0], tx_samples[::])

    # input buffer
    tau     = 0.                        # initial timing offset estimate
    dtau    = 0.                        # initial timing _rate_ offset estimate
    buf     = np.zeros(5, dtype=np.complex64) # filter buffer
    th      = np.array([-2., -1., 0., 1., 2.]) # time vector for interpolating filter
    w       = np.sqrt(np.hamming(5).T)  # window function for interpolating filter
    alpha   = 0.005                    # loop filter bandwidth (timing _rate_ adjustment factor)
    beta    = 2*np.sqrt(alpha)          # (timing _phase_ adjustment factor)
    counter = sample_delay + 1          # interpolating filter adds delay
    mf_samples       = np.zeros(len(mf_samples_with_offset), dtype=np.complex64)
    buf_dz  = [0.,0.,0.]

    dtau_vect = np.zeros(len(mf_samples_with_offset), dtype=np.complex64)
    tau_vect = np.zeros(len(mf_samples_with_offset), dtype=np.complex64)

    for i in range(1, len(mf_samples_with_offset)):
        # push sample into interpolating filter
        buf[:-1] = buf[1:]
        buf[-1] = mf_samples_with_offset[i]

        # interpolate matched filter output
        hi   = np.sinc(th - tau) * w  # interpolating filter coefficients
        mf_samples[i] = np.dot(buf, np.flip(hi))    # compute matched filter output

        # take (approximate) derivative of filter output
        buf_dz[:-1] = buf_dz[1:]
        buf_dz[-1] = mf_samples[i]
        dz = -np.dot(buf_dz, np.array([-1, 0, 1]))

        # determine if an output sample needs to be computed
        counter = counter + 1
        if counter >= samples_per_symbol:
            # decrement counter by samples per symbol
            counter = counter - samples_per_symbol

            # compute timing error signal, accounting for delay
            err = np.tanh( (dz * np.conj(mf_samples[i-1])).real )

            # update timing estimate
            tau = tau + alpha*err

            # update timing rate change
            dtau = dtau + alpha * err
            tau  = tau  +  beta * err

        # update timing error
        tau = tau + dtau/samples_per_symbol

        # save results for plotting
        dtau_vect[i] = dtau
        tau_vect[i] = tau

    plt.figure()
    plt.subplot(211)
    plt.title("Tau")
    plt.plot(tau_vect)

    plt.subplot(212)
    plt.title("DTau")
    plt.plot(dtau_vect)

    # Plot the symbols, Tx symbols, and Rx symbols
    plt.figure()
    plt.subplot(121)
    plt.title("QPSK symbols, RRC filtering")
    plt.xlabel("Samples")
    plt.ylabel("Magnitude")

    plt.scatter(mf_samples_with_offset.real[sample_delay::samples_per_symbol], \
                mf_samples_with_offset.imag[sample_delay::samples_per_symbol], \
                color='r', marker='x', label='Rx before timing recovery')

    plt.scatter(tx_samples.real[sample_delay::samples_per_symbol], \
                tx_samples.imag[sample_delay::samples_per_symbol], marker='x', label='Tx after filter')

    # Only plot the second half of the symbols
    second_half = int(num_symbols/2.) * samples_per_symbol
    plt.scatter(mf_samples.real[second_half::samples_per_symbol], \
                mf_samples.imag[second_half::samples_per_symbol], marker='x', label='Rx after timing recovery')

    plt.scatter(symbols.real[::samples_per_symbol], \
                symbols.imag[::samples_per_symbol], marker='x', label='Symbols')
    plt.legend(loc='best')

    # Plot the time domain signal
    plt.subplot(122)
    plt.title("QPSK symbols, After MF")
    plt.xlabel("I")
    plt.ylabel("Q")
    plt.plot(mf_samples.real[:250])
    plt.plot(mf_samples.imag[:250])
    plt.show()