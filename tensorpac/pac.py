"""Main PAC class."""
import numpy as np
from scipy.signal import hilbert

from .utils import PacVec
from .pacstr import pacstr
from .spectral import spectral
from .methods import ComputePac
from .surrogates import ComputeSurogates
from .normalize import normalize


class Pac(object):
    """Compute Phase-Amplitude Coupling (PAC) using tensors.

    Computing PAC is assessed in three steps : compute the real PAC, compute
    surrogates and finally, because PAC is very sensible to the noise, correct
    the real PAC by the surrogates. This implementation is modular i.e. it lets
    you choose among a large range of possible combinations.

    Kargs:
        idpac: tuple/list, optional, (def: (1, 1, 3))
            Choose the combination of methods to use in order to extract PAC.
            This tuple must be composed of three integers where each one them
            refer

            * First digit: refer to the pac method:

                - '1': Mean Vector Length (MVL) [#f1]_
                - '2': Kullback-Leibler Divergence (KLD) [#f2]_
                - '3': Heights Ratio (HR) [#f3]_
                - '4': ndPAC [#f4]_
                - '5': Phase Synchrony [#f3]_
                - '6': ERPAC [#f6]_

            * Second digit: refer to the method for computing surrogates:

                - '0': No surrogates
                - '1': Swap phase/amplitude across trials [#f2]_
                - '2': Swap amplitude time blocks [#f5]_
                - '3': Shuffle amplitude and phase time-series
                - '4': Shuffle phase time-series
                - '5': Shuffle amplitude time-series
                - '6': Time lag [#f1]_
                - '7': Circular shifting [NOT IMPLEMENTED]

            * Third digit: refer to the normalization method for correction:

                - '0': No normalization
                - '1': Substract the mean of surrogates
                - '2': Divide by the mean of surrogates
                - '3': Substract then divide by the mean of surrogates
                - '4': Z-score

        fpha, famp: list/tuple/array, optional, (def: [2, 4] and [60, 200])
            Frequency vector for the phase and amplitude. Here you can use
            several forms to define those vectors :

                * Basic list/tuple (ex: [2, 4] or [8, 12]...)
                * List of frequency bands (ex: [[2, 4], [5, 7]]...)
                * Dynamic definition : (start, stop, width, step)
                * Range definition (ex : np.arange(3) => [[0, 1], [1, 2]])

        dcomplex: string, optional, (def: 'hilbert')
            Method for the complex definition. Use either 'hilbert' or
            'wavelet'.

        filt: string, optional, (def: 'fir1')
            Filtering method (only if dcomplex is 'hilbert'). Choose either
            'fir1', 'butter' or 'bessel'

        cycle: tuple, optional, (def: (3, 6))
            Control the number of cycles for filtering (only if dcomplex is
            'hilbert'). Should be a tuple of integers where the first one
            refers to the number of cycles for the phase and the second for the
            amplitude [#f5]_.

        filtorder: int, optional, (def: 3)
            Filter order for the Butterworth and Bessel filters (only if
            dcomplex is 'hilbert').

        width: int, optional, (def: 7)
            Width of the Morlet's wavelet.

        nbins: int, optional, (def: 18)
            Number of bins for the KLD and HR PAC method [#f2]_ [#f3]_

        nblocks: int, optional, (def: 2)
            Number of blocks for splitting the amplitude. Only active is
            the surrogate method is 2 [#f5]_.

    .. warning::
        * The ndPac [#f4]_ include a fast and reliable statistical test. As a
          result, if the ndPAC is choosed as the main PAC method, surrogates
          and normalization will be deactivate.

        * The phase in a particular frequency band can either be extracted
          using wavelet convolution or filtering followed by the Hilbert
          transform. As a result, every filtering related input (cycle, filt,
          filtorder) are going to be active if the complex decomposition is
          Hilbert.

    Methods:
        self.filt:
            Filt the data in the specified frequency bands.

        self.fit:
            Run the PAC on filtered data.

        self.filtfit:
            Filt the data then compute PAC on it.

        self.comodulogram:
            Plot PAC.

    .. rubric:: Footnotes
    .. [#f1] `Canolty et al, 2006 <http://www.ncbi.nlm.nih.gov/pmc/articles/
       PMC2628289/>`_
    .. [#f2] `Tort et al, 2010 <http://www.ncbi.nlm.nih.gov/pmc/articles/
       PMC2941206/>`_
    .. [#f3] `Lakata et al, 2005 <https://www.ncbi.nlm.nih.gov/pubmed/
       15901760>`_
    .. [#f4] `Ozkurt et al, 2012 <http://www.ncbi.nlm.nih.gov/pubmed/
       22531738/>`_
    .. [#f5] `Bahramisharif et al, 2013 <http://www.jneurosci.org/content/33/
       48/18849.short/>`_
       [#f6] `Voytek et al, 2013 <https://www.ncbi.nlm.nih.gov/pubmed/
       22986076>`_
    """

    ###########################################################################
    #                              __FCN__
    ###########################################################################
    def __init__(self, idpac=(1, 1, 3), fpha=[2, 4], famp=[60, 200],
                 dcomplex='hilbert', filt='fir1', cycle=(3, 6), filtorder=3,
                 width=7, nbins=18, nblocks=2):
        """Check and initialize."""
        # ----------------- CHECKING -----------------
        # Pac methods :
        self._idcheck(idpac)
        # Frequency checking :
        self.fpha, self.famp = PacVec(fpha, famp)
        self.xvec, self.yvec = self.fpha.mean(1), self.famp.mean(1)

        # Check spectral properties :
        self._speccheck(filt, dcomplex, filtorder, cycle, width)

        # ----------------- SELF -----------------
        self.nbins, self.nblocks = int(nbins), int(nblocks)

    def __str__(self):
        """String representation."""
        pass

    ###########################################################################
    #                              METHODS
    ###########################################################################
    def filter(self, sf, x, axis=-1, ftype='phase', njobs=-1):
        """Filt the data in the specified frequency bands.

        Args:
            sf: float
                The sampling frequency.

            x: np.ndarray
                Array of data.

        Kargs:
            axis: int, optional, (def: -1)
                Location of the time axis.

            ftype: string, optional, (def: 'phase')
                Specify if you want to extract phase ('phase') or the amplitude
                ('amplitude').

            njobs: int, optional, (def: -1)
                Number of jobs to compute PAC in parallel. For very large data,
                set this parameter to 1 in order to prevent large memory usage.
        Returns:
            xfilt: np.ndarray
                The filtered data of shape (n_frequency, ...)
        """
        # --------------------------------------------------------------
        # keepfilt=False,
        # keepfilt: bool, optional, (def: False)
        #     Specify if you only want the filtered data (True) or either
        #     the angle (ftype='phase') or the modulus (ftype='amplitude').
        # --------------------------------------------------------------
        # Sampling frequency :
        if not isinstance(sf, (int, float)):
            raise ValueError("The sampling frequency must be a float number.")
        else:
            sf = float(sf)
        # Switch between phase or amplitude :
        if ftype is 'phase':
            xfilt = spectral(x, sf, self.fpha, axis, 'pha', self._dcomplex,
                             self._filt, self._filtorder, self._cycle[0],
                             self._width, njobs)
        elif ftype is 'amplitude':
            xfilt = spectral(x, sf, self.famp, axis, 'amp', self._dcomplex,
                             self._filt, self._filtorder, self._cycle[1],
                             self._width, njobs)
        else:
            raise ValueError("ftype must either be 'phase' or 'amplitude.'")
        return xfilt

    def fit(self, sf, pha, amp, axis=1, traxis=0, nperm=200, correct=False,
            njobs=-1):
        """Compute PAC on filtered data.

        Args:
            sf: float
                The sampling frequency.

            pha, amp: np.ndarray
                Array of filtered data with respectively a shape of (npha, ...)
                and (namp, ...). If you want to compute PAC locally i.e. on the
                same electrode, x=pha=amp. For distant coupling, pha and
                amp could be different but still must to have the same shape.

        Kargs:
            axis: int, optional, (def: 1)
                Dimension where is located the time axis. By default, the axis
                will be consider as well.

            traxis: int, optional, (def: 0)
                Dimension where is located the trial axis. By default the next-
                to-last axis is consider as the trial axis.

            nperm: int, optional, (def: 200)
                Number of surrogates to compute.

            correct: bool, optional, (def: True)
                Correct the PAC estimation XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

            njobs: int, optional, (def: -1)
                Number of jobs to compute PAC in parallel. For very large data,
                set this parameter to 1 in order to prevent large memory usage.

        .. warning::
            * Surrogates are only going to be computed if the second and third
              digits are no 0.

            * The ndPAC use a p value and every non-significant PAC estimation
              is set to zero. This p value is computed as 1/nperm.

            * The traxis argument is only used if you picked up the surrogates
              method 1: "swap phase and amplitude trials [#f2]_"

            * Basically, the surrogate evaluation proposed by [#f5]_ split the
              amplitude into two equal parts, then swap those two blocks. But
              the nblocks parameter allow to split into a larger number.
        """
        # Compute pac :
        pacargs = (self.idpac[0], self.nbins, 1/nperm)
        pac = ComputePac(pha, amp, *pacargs)

        # Compute surogates :
        if self._csuro:
            surargs = (self.idpac[1], axis, traxis, self.nblocks)
            suro = ComputeSurogates(pha, amp, surargs, pacargs, nperm, njobs)

            # Normalize pac by surrogates :
            pac = normalize(pac, np.mean(suro, axis=0),
                            np.std(suro, axis=0), self.idpac[2])

            # Compute statistics :

        if correct:
            pac[pac < 0.] = 0.

        return pac, None

    def filterfit(self, sf, xpha, xamp, axis=1, traxis=0, nperm=200,
                  correct=False, njobs=-1):
        """Filt the data then compute PAC on it.

        Args:
            sf: float
                The sampling frequency.

            xpha, xamp: np.ndarray
                Array of data for computing PAC. xpha is the data used for
                extracting phases and xamp, amplitudes. Both arrays must have
                the same shapes. If you want to compute PAC locally i.e. on the
                same electrode, x=xpha=xamp. For distant coupling, xpha and
                xamp could be different but still must to have the same shape.

        Kargs:
            axis: int, optional, (def: 1)
                Dimension where is located the time axis. By default, the axis
                will be consider as well.

            traxis: int, optional, (def: 0)
                Dimension where is located the trial axis. By default the next-
                to-last axis is consider as the trial axis.

            nperm: int, optional, (def: 200)
                Number of surrogates to compute.

            correct: bool, optional, (def: True)
                Correct the PAC estimation XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

            njobs: int, optional, (def: -1)
                Number of jobs to compute PAC in parallel. For very large data,
                set this parameter to 1 in order to prevent large memory usage.

        .. warning::
            * Surrogates are only going to be computed if the second and third
              digits are no 0.

            * The ndPAC use a p value and every non-significant PAC estimation
              is set to zero. This p value is computed as 1/nperm.

            * The traxis argument is only used if you picked up the surrogates
              method 1: "swap phase and amplitude trials [#f2]_"

            * Basically, the surrogate evaluation proposed by [#f5]_ split the
              amplitude into two equal parts, then swap those two blocks. But
              the nblocks parameter allow to split into a larger number.
        """
        # Shape checking :
        if xpha.shape != xamp.shape:
            raise ValueError("The shape of xpha and xamp must be equals.")
        # Extract phase (npha, ...) and amplitude (namp, ...) :
        pha = self.filter(sf, xpha, axis, 'phase', njobs)
        amp = self.filter(sf, xamp, axis, 'amplitude', njobs)

        # Special cases :
        if self._idpac[0] == 5:
            amp = np.angle(hilbert(amp, axis=-1))

        # Compute pac :
        return self.fit(sf, pha, amp, axis+1, traxis+1, nperm, correct, njobs)

    def comodulogram(self, pac, title='', cmap='viridis', clim=None, vmin=None,
                     vmax=None, under=None, over=None, bad=None, pvalues=None):
        """Plot PAC using comodulogram.

        Args:
            pac: np.ndarray
                PAC array of shape (pha, namp)

        Kargs:
            title: string, optional, (def: '')
                Title of the plot.

            cmap: string, optional, (def: 'viridis')
                Name of one Matplotlib's colomap.

            clim: tuple, optional, (def: None)
                Limit of the colorbar.

            vmin: float, optional, (def: None)
                Threshold under which set the color to the uner parameter.

            vmax: float, optional, (def: None)
                Threshold over which set the color in the over parameter.

            under: string, optional, (def: None)
                Color for values under the vmin parameter.

            over: string, optional, (def: None)
                Color for values over the vmax parameter.

            pvalues: np.ndarray, optional, (def: None)
                P-values to use for masking PAC values. The shape of this
                parameter must be the same as the shape as pac.

            bad: string, optional, (def: None)
                Color for non-significant values.

        Returns:
            gca: axes
                The current matplotlib axes.
        """
        import matplotlib.pyplot as plt
        plt.pcolormesh(self.xvec, self.yvec, pac, cmap=cmap)
        plt.axis('tight')
        plt.xlabel('Frequency for phase (hz)')
        plt.ylabel('Frequency for amplitude (hz)')
        plt.title(title)
        plt.clim(vmin=vmin, vmax=vmax)
        plt.colorbar()
        return plt.gca()

    ###########################################################################
    #                              CHECKING
    ###########################################################################
    def _idcheck(self, idpac):
        """Check the idpac parameter."""
        idpac = np.atleast_1d(idpac)
        self._csuro = True
        if not all([isinstance(k, int) for k in idpac]) and (len(idpac) != 3):
            raise ValueError("idpac must be a tuple/list of 3 integers.")
        else:
            # Ozkurt PAC case :
            if idpac[0] == 4:
                idpac[1], idpac[2] = 0, 0
                self._csuro = False
            if (idpac[1] == 0) or (idpac[2] == 0):
                self._csuro = False
        self._idpac = idpac
        self.method, self.surro, self.norm = pacstr(idpac)

    def _speccheck(self, filt=None, dcomplex=None, filtorder=None, cycle=None,
                   width=None):
        """Check spectral parameters."""
        # Check the filter name :
        if filt is not None:
            if filt not in ['fir1', 'butter', 'bessel']:
                raise ValueError("filt must either be 'fir1', 'butter' or "
                                 "'bessel'")
            else:
                self._filt = filt
        # Check cycle :
        if cycle is not None:
            cycle = np.asarray(cycle)
            if (len(cycle) is not 2) or not cycle.dtype == int:
                raise ValueError("Cycle must be a tuple of two integers.")
            else:
                self._cycle = cycle
        # Check complex decomposition :
        if dcomplex is not None:
            if dcomplex not in ['hilbert', 'wavelet']:
                raise ValueError("dcomplex must either be 'hilbert' or "
                                 "'wavelet'.")
            else:
                self._dcomplex = dcomplex
        # Convert filtorder :
        if filtorder is not None:
            self._filtorder = int(filtorder)
        # Convert Morlet's width :
        if width is not None:
            self._width = int(width)

    ###########################################################################
    #                              PROPERTIES
    ###########################################################################
    # ----------- IDPAC -----------
    @property
    def idpac(self):
        """Get the idpac value."""
        return self._idpac

    @idpac.setter
    def idpac(self, value):
        """Set idpac value."""
        self._idcheck(value)

    # ----------- FILT -----------
    @property
    def filt(self):
        """Get the filt value."""
        return self._filt

    @filt.setter
    def filt(self, value):
        """Set filt value."""
        self._speccheck(filt=value)

    # ----------- DCOMPLEX -----------
    @property
    def dcomplex(self):
        """Get the dcomplex value."""
        return self._dcomplex

    @dcomplex.setter
    def dcomplex(self, value):
        """Set dcomplex value."""
        self._speccheck(dcomplex=value)

    # ----------- CYCLE -----------
    @property
    def cycle(self):
        """Get the cycle value."""
        return self._cycle

    @cycle.setter
    def cycle(self, value):
        """Set cycle value."""
        self._speccheck(cycle=value)

    # ----------- FILTORDER -----------
    @property
    def filtorder(self):
        """Get the filtorder value."""
        return self._filtorder

    @filtorder.setter
    def filtorder(self, value):
        """Set filtorder value."""
        self._speccheck(filtorder=value)

    # ----------- WIDTH -----------
    @property
    def width(self):
        """Get the width value."""
        return self._width

    @width.setter
    def width(self, value):
        """Set width value."""
        self._width = value

