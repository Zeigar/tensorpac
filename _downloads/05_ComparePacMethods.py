"""
======================
PAC methods comparison
======================

Note that this script do not perform any correction by surrogates.
"""
from __future__ import print_function
import matplotlib.pyplot as plt
from tensorpac.utils import pac_signals
from tensorpac import Pac
plt.style.use('seaborn-paper')

# First, we generate a dataset of signals artificially coupled between 10hz
# and 100hz. By default, this dataset is organized as (ndatasets, npts) where
# npts is the number of time points.
n = 10  # number of datasets
sf = 1024  # sampling frequency
npts = 3000  # Number of time points
data, time = pac_signals(sf=sf, fpha=10, famp=100, noise=3, ndatasets=n,
                         dpha=10, damp=10, npts=npts)

# First, let's use the MVL, without any further correction by surrogates :
p = Pac(fpha=(1, 30, 1, 1), famp=(60, 160, 5, 5), dcomplex='wavelet', width=12)

# Now, we want to compare PAC methods, hence it's useless to systematically
# filter the data. So we extract the phase and the amplitude only once :
phases = p.filter(sf, data, axis=1, ftype='phase')
amplitudes = p.filter(sf, data, axis=1, ftype='amplitude')

for i, k in enumerate([1, 2, 3, 4, 5]):
    # Change the pac method :
    p.idpac = (k, 0, 0)
    print('-> PAC using ' + str(p))
    # Compute only the PAC without filtering :
    xpac, _ = p.fit(phases, amplitudes, axis=2)
    # Plot :
    plt.subplot(3, 2, k)
    p.comodulogram(xpac.mean(-1), title=p.method, cmap='Spectral_r')

plt.show()
