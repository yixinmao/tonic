#!/usr/bin/env python
"""
vic.py
"""

from __future__ import print_function
import os
import tempfile
import subprocess
from datetime import datetime
import pandas as pd

default_vic_valgrind_error_code = 125
default_vic_valgrind_suppressions_path = 'vic_valgrind_suppressions.supp'


# -------------------------------------------------------------------- #
class VICRuntimeError(RuntimeError):
    pass
# -------------------------------------------------------------------- #


# -------------------------------------------------------------------- #
class VIC(object):
    def __init__(self, executable):
        if os.path.isfile(executable) and os.access(executable, os.X_OK):
            self.executable = executable
            self.version = self._get_version()
            self.options = self._get_options()
            self.args = []
            self.argstring = ''
        else:
            raise VICRuntimeError('%s is not a valid executable' % executable)

    def _get_version(self):
        """Get the version of VIC from the executable"""
        self._call_vic('-v')
        return self.stdout

    def _get_options(self):
        """Get the compile time options of VIC from the executable"""
        self._call_vic('-o')
        return self.stdout

    def run(self, global_param, logdir=None, **kwargs):
        """
        Run VIC with specified global parameter file.
        Parameters
        ----------
        global_param: str
            Either a path to a VIC global parameter file or a multiline string
            including VIC global parameter options.
        logdir : str, optional
            Path to write log files to.
        **kwargs : key=value, optional
            Keyword arguments to pass to the VIC executable. Valid options are:
                mpi_proc : int
                    Specifies number of processors for MPI (must be integer or
                    None).
                    Default is 1 processor.
                mpi_exe : str
                    If mpi_proc is not 1, then this is the path of MPI exe
                valgrind : str or bool
                    Specifies path to valgrind executable. If bool and True,
                    valgrind will be used without specifying the full path.
        Returns
        --------
        returncode : int
            Return error code from VIC.
        Examples
        --------
        retcode = vic.run(global_param_path, logdir=".", mpi_proc=4)
        """

        if os.path.isfile(global_param):
            global_param_file = global_param
        else:
            # global_param is a string
            f, global_param_file = tempfile.mkstemp(prefix='vic.global.param.',
                                                    suffix='.txt',
                                                    text=True)
            with open(global_param_file, mode='w') as f:
                f.write(global_param)

        self._call_vic('-g', global_param_file, **kwargs)

        if logdir:
            now = datetime.now()
            seconds = (now - now.replace(hour=0, minute=0, second=0,
                                         microsecond=0)).total_seconds()
            timestr = "%s_%05.f" % (now.strftime("%Y%m%d"), seconds)
            with open(os.path.join(logdir, 'stdout_{0}.txt'.format(timestr)),
                      mode='wb') as f:
                f.write(self.stdout)
            with open(os.path.join(logdir, 'stderr_{0}.txt'.format(timestr)),
                      mode='wb') as f:
                f.write(self.stderr)

        return self.returncode

    def _call_vic(self, *args, **kwargs):

        self.args = []

        # Get mpi info
        mpi_proc = kwargs.pop('mpi_proc', None)
        if isinstance(mpi_proc, int):
            if mpi_proc == 1:
                mpi_proc = None
        mpi_exe = kwargs.pop('mpi_exe', None)
        if mpi_proc is not None:
            if not isinstance(mpi_proc, int):
                raise TypeError("number of processors must be specified as an"
                                "integer")
            self.args.extend([mpi_exe, '-np', '%.0d' % mpi_proc])

        # Get valgrind info
        valgrind = kwargs.pop('valgrind', None)
        if valgrind:
            if valgrind is True:
                valgrind = 'valgrind'
            errorcode = os.getenv('VIC_VALGRIND_ERROR',
                                  default_vic_valgrind_error_code)
            self.args.extend([valgrind, '-v', '--leak-check=full',
                             '--error-exitcode={0}'.format(errorcode)])

            suppressions = os.getenv('VIC_VALGRIND_SUPPRESSIONS',
                                     default_vic_valgrind_suppressions_path)
            if os.path.isfile(suppressions):
                self.args.extend(['--suppressions={0}'.format(suppressions)])

        # if there are kwargs left, we don't know what to do with them so
        # raise an error
        if kwargs:
            raise ValueError('Unknown argument(s): %s' % ', '.join(kwargs.keys()))

        self.args += [self.executable] + [a for a in args]

        # set the args attribute

        self.argstring = ' '.join(self.args)

        proc = subprocess.Popen(self.argstring,
                                shell=True,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE)
        retvals = proc.communicate()

        self.stdout = retvals[0]
        self.stderr = retvals[1]
        self.returncode = proc.returncode
# -------------------------------------------------------------------- #


# -------------------------------------------------------------------- #
def read_vic_ascii(filepath, header=True, parse_dates=True,
                   datetime_index=None, names=None, **kwargs):
    """Generic reader function for VIC ASCII output with a standard header
    filepath: path to VIC output file
    header (True or False):  Standard VIC header is present
    parse_dates (True or False): Parse dates from file
    datetime_index (Pandas.tseries.index.DatetimeIndex):  Index to use as
    datetime index names (list like): variable names
    **kwargs: passed to Pandas.read_table

    returns Pandas.DataFrame
    """
    kwargs['header'] = None

    if header:
        kwargs['skiprows'] = 6

        # get names
        if names is None:
            with open(filepath) as f:
                # skip lines 0 through 5
                for _ in range(5):
                    next(f)

                # process header
                names = next(f)
                names = names.strip('#').replace('OUT_', '').split()

    kwargs['names'] = names

    if parse_dates:
        time_cols = ['YEAR', 'MONTH', 'DAY']
        if 'HOUR' in names:
            time_cols.append('HOUR')
        kwargs['parse_dates'] = {'datetime': time_cols}
        kwargs['index_col'] = 0

    df = pd.read_table(filepath, **kwargs)

    if datetime_index is not None:
        df.index = datetime_index

    return df
# -------------------------------------------------------------------- #
