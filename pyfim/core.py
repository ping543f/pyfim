#    This code is part of pyFIM (http://www.github.com/schlegelp/pyfim), a
#    package to analyze FIMTrack data (fim.uni-muenster.de). For full
#    acknowledgments and references, please see the GitHub repository.
#
#    Copyright (C) 2018 Philipp Schlegel
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.


import os
from io import IOBase

import pandas as pd
import numpy as np

import re

# Load analysis scripts
from pyfim import analysis as fim_analysis
from pyfim import plot as fim_plot
from pyfim import utils

# Load default values
from pyfim import config
defaults = config.default_parameters

# Load progress bar
from tqdm import tqdm
if utils.is_jupyter():
    from tqdm import tqdm_notebook, tnrange
    tqdm = tqdm_notebook
    trange = tnrange

import logging
module_logger = logging.getLogger('pyfim')
module_logger.setLevel(logging.INFO)
if len( module_logger.handlers ) == 0:
    # Generate stream handler
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    # Create formatter and add it to the handlers
    formatter = logging.Formatter(
                '%(levelname)-5s : %(message)s (%(name)s)')
    sh.setFormatter(formatter)
    module_logger.addHandler(sh)


class Collection:
    """ Collection of experiments. This allows you to easily collect and plot
    data from multi experiments.

    Examples
    --------
    >>> # Initialise two experiments from CSVs in a folder
    >>> exp1 = pyfim.Experiment( 'users/data/genotype1' )
    >>> exp2 = pyfim.Experiment( 'users/data/genotype2' )
    >>> # Initialise collection and add data
    >>> c = pyfim.Collection()
    >>> c.add_data( exp1, 'Genotype I')
    >>> c.add_data( exp2, 'Genotype II')
    >>> # Get a summary
    >>> c
    ... <class 'pyfim.core.Collection'> with 2 experiments:
    ...    name         n_objects  n_frames
    ... 0  Genotype I          47      1800
    ... 1  Genotype II         46      1800
    ... Available parameters: mom_y, perimeter, peristalsis_frequency,
    ... radius_3, pause_turns, spinepoint_2_x, acc_dst, ...
    >>> # Access data
    >>> c.peristalsis_frequency
    >>> # Plot as boxplot
    >>> ax = c.peristalsis_frequency.plot(kind='box')
    >>> plt.show()

    """

    def __init__(self):
        self.experiments = []
        pass


    def add_data(self, x, label=None, keep_raw=False):
        """ Add data (e.g. a genotype) to this analysis.

        Parameters
        ----------
        x :         {filename, folder, file object, pyfim.Experiment}
                    Provide either:
                        - a CSV file name
                        - a CSV file object
                        - list of the above
                        - single folder
                        - single pyfim.Experiment object
                    Lists of files will be merged and objects (columns) will
                    be renumbered.
        label :     str, optional
                    Label of this data set.
        keep_raw :  bool, optional
                    If False, will discard raw data after extraction to save
                    memory. Only relevant if x is not an pyfim.Experiment.

        Returns
        -------
        Nothing

        """
        if not label:
           label = 'exp_{0}'.format( len( self.experiments ) + 1 )

        if not isinstance( x, Experiment ):
            exp = Experiment(x, keep_raw=keep_raw)
        else:
            exp = x

        setattr(self, label, exp )

        self.experiments.append(label)

        self.extract_data()


    def summary(self):
        """ Gives a summary of the data in this analysis.
        """

        to_summarize = ['n_objects','n_frames']

        return pd.DataFrame( [ [exp] + [ getattr( getattr(self, exp), p ) for p in to_summarize ] for exp in self.experiments ],
                             columns=['name']+to_summarize )


    def __str__(self):
        return self.__repr__()


    def __repr__(self):
        return '{0} with {1} experiments: \n {2} \n Available parameters: {3}'.format(type(self),
                                                                                     len(self.experiments),
                                                                                     str(self.summary()),
                                                                                     ', '.join(self.parameters) )

    @property
    def parameters(self):
        """Returns parameters that all experiments have in common."""
        all_params = [ set( getattr(self, exp).parameters )
                                for exp in self.experiments ]
        if all_params:
            return np.array( list(all_params[0].union(*all_params) ) )
        else:
            return []


    def extract_data(self):
        """ Get the mean over all parameters.
        """

        # Get basic parameter from raw data
        for param in self.parameters:
            data = [ ]
            for e in self.experiments:
                # Collect data
                exp = getattr(self, e)
                values = getattr( exp, param )
                if values.ndim == 1:
                    means = values.values
                else:
                    means = values.mean().values
                data.append( means )
            df = pd.DataFrame( data, index= self.experiments ).T
            setattr(self, param, df)


    def plot(self, param=None, **kwargs):
        """ Plots a set of parameters from this pyFIM Collection.

        Parameters
        ----------
        param : {str, list of str, None}, optional
                Parameters to plot. If None, will plot a default selection of
                parameters: acc_dst, dst_to_origin, head_bends, bending_strength,
                peristalsis_frequency, peristalsis_efficiency, stops, pause_turns,
                velocity

        **kwargs
                Will be passed to pandas.DataFrame.plot

        Returns
        -------
        matplotlib.Axes

        """
        return fim_plot.plot_parameters(self, param, **kwargs)


class Experiment:
    """ Class that holds raw data for a set of data.

    Parameters
    ----------
    f :         {filename, folder, file object}
                    Provide either:
                        - a CSV file name
                        - a CSV file object
                        - single folder
                        - list of the above
                Lists of files will be merged and objects (columns) will be
                renumbered.
    keep_raw :  bool, optional
                If False, will discard raw data after extraction to save
                memory.
    include_subfolders : bool, optional
                         If True and folder is provided, will also search
                         subfolders for .csv files.

    Examples
    --------
    >>> # Generate an experiment from all csv files in one folder
    >>> folder = 'users/downloads/genotype1'
    >>> exp = pyfim.Experiment( folder )
    >>> # See available analysis
    >>> exp.parameters
    ... ['acc_dst', 'acceleration', 'area', 'bending',...
    >>> # Access data
    >>> exp.dst_to_origin.head()
    ...    object_1  object_13  object_15  object_18  object_19  \
    ... 0   0.00000    0.00000        NaN        NaN        NaN
    ... 1   2.23607    0.00000        NaN        NaN        NaN
    ... 2   3.60555    1.41421        NaN        NaN        NaN
    ... 3   3.60555    2.82843        NaN        NaN        NaN
    ... 4   4.47214    4.24264        0.0        NaN        NaN
    >>> # Plot data individual objects over time
    >>> ax = exp.dst_to_origin.plot()
    >>> plt.show()
    >>> # Get mean of all values
    >>> exp.mean()

    """

    def __init__(self, f, keep_raw=False, include_subfolders=False):
        # Make sure we have files or filenames
        if f:
            f = _parse_files(f, include_subfolders)

            if len(f) == 0:
                raise ValueError('No files found')
        else:
            # This is for when we want to initialise an empty experiment
            self.parameters = []
            self._original_params = []
            return

        # Get the data from each individual file
        data = [ pd.read_csv(fn, sep=defaults['DELIMITER'], index_col=0) for fn in tqdm(f, desc='Reading files', leave=False) ]

        # Merge - make sure the indices match up
        self.raw_data = pd.concat( data, axis=1, ignore_index=False, join='outer' )

        # join='outer' makes sure that if we have an uneven number of frames,
        # they will be aligned and empty frames will be filled with NaN
        # However, this also messes up the order -> will have to fix that
        fixed_ix = sorted( self.raw_data.index, key = lambda x : self._index_sorter ( x ) )
        self.raw_data = self.raw_data.loc[fixed_ix]

        self.raw_data.columns = [ 'object_{0}'.format(i) for i in range( self.raw_data.shape[1] ) ]

        self.extract_data()

        if not keep_raw:
            del self.raw_data

    def _index_sorter( self, x):
        """ Helper function to fix pandas indices. After merging frames are
        messed up:

        mom_x(0)
        mom_x(10)
        mom_x(11)
        ...

        Returns
        -------
        parameter (str) :     e.g. "mom_x"
        frame (int) :         e.g. 10
        """

        groups = re.search('(.*?)\((.*?)\)', x).groups()

        return ( groups[0], int(groups[1]) )


    def extract_data(self):
        """ Extracts parameters from .csv file.
        """

        if isinstance( getattr(self, 'raw_data', None) , type(None) ):
            raise ValueError('No raw data to analyze found.')

        # Find all parameters
        self.parameters = sorted (set( [ p[ : p.index('(') ] for p in self.raw_data.index ] ) )

        # Keep track of original parameters (make sure to use a copy)
        self._original_params = list( self.parameters )

        # Go over all parameters
        for p in tqdm( self.parameters, desc='Extracting data', leave=False ):
            # Extract values
            values = self.raw_data.loc[ [ p in i for i in self.raw_data.index ] ]

            # Change the index to frames
            values.index = list(range( values.shape[0] ))

            # Add data as attribute
            setattr(self, p, values )

        # Perform data clean up
        self.clean_data()

        # Perform additional, "higher-level" analyses
        for param in tqdm(fim_analysis.__all__, desc='Performing additional analyses', leave=False):
            func = getattr( fim_analysis, param )
            setattr(self, param, func( self ) )
            self.parameters.append( param )

        self.parameters = sorted( self.parameters )


    @property
    def objects(self):
        """ Returns the tracked objects in this experiment. Please note that
        the order is not as in the DataFrames.
        """
        all_cols = []
        for p in self.parameters:
            values = getattr(self, p )
            if isinstance(values, pd.DataFrame):
                all_cols.extend( values.columns.values )

        return sorted( list( set(all_cols ) ) )


    @property
    def n_objects(self):
        """ Returns the number of objects tracked in this experiment.
        """

        return getattr(self, self.parameters[0] ).shape[1]


    @property
    def n_frames(self):
        """ Returns the number of frames in this experiment.
        """

        return getattr(self, self.parameters[0] ).shape[0]


    def clean_data(self):
        """ Cleans up the data.
        """
        frames_before = self.n_frames
        obj_before = self.n_objects

        # Get objects that have at an all NaN column in any parameter
        has_all_nans = [ obj for obj in self.objects if 0 in self[obj].count().values ]

        # Will use the "head_x" parameter to determine track length
        # -> some other parameters (e.g. "go_phase") vary in length
        long_enough = [ obj for obj in self.objects if
                        getattr(self, 'head_x')[obj].count() >= defaults['MIN_TRACK_LENGTH']
                        and obj not in has_all_nans]

        # Iterate over parameters and clean-up if necessary
        for p in tqdm(self.parameters, desc='Cleaning data', leave=False):
            # Get values
            values = getattr(self, p)

            # Drop objects that have all NaNs
            values = values.drop( has_all_nans, axis=1 )

            # Remove object (columns) too few data points
            if defaults['MIN_TRACK_LENGTH']:
                # Remove columns with fewer than minimum values
                values = values.loc[:, long_enough ]

            # Remove first X entries
            if defaults['CUT_TABLE_HEAD']:
                values = values.iloc[ defaults['CUT_TABLE_HEAD'] : ]

            # Remove last X entries
            if defaults['CUT_TABLE_TAIL']:
                values = values.iloc[ : defaults['CUT_TABLE_TAIL'] ]

            # Convert to mm/mm^2
            if defaults['PIXEL2MM']:
                if p in defaults['SPATIAL_PARAMS']:
                    values *= defaults['PIXEL_PER_MM']
                elif p in defaults['AREA_PARAMS']:
                    values = np.sqrt(values) * defaults['PIXEL_PER_MM']

            # Interpolate gaps (i.e. a sub-threshold gap between two above
            # threshold stretches) in thresholded parameters
            if defaults['FILL_GAPS'] and p in defaults['THRESHOLDED_PARAMS']:
                # Keep track of zeros
                zeros = values == 0.0
                # Set zeros to "NaN"
                values[ values == 0.0 ] = np.nan
                # Fill gaps with previous value ("forward fill")
                values = values.fillna( method='ffill',
                                        axis=0,
                                        limit=defaults['MAX_GAP_SIZE'])
                # Set zeros that stayed zeros back to zero
                values[ (zeros) & ( values.isnull() ) ] = 0.0

            # Write values back
            setattr( self, p, values )

        module_logger.info('Data clean-up dropped {0} objects and {1} frames'.format( obj_before-self.n_objects, frames_before-self.n_frames ))


    def __str__(self):
        return self.__repr__()


    def __repr__(self):
        return '{0} with: {1} objects; {2} frames. Available parameters: {3}'.format(type(self), self.n_objects, self.n_frames, ', '.join(self.parameters) )


    def analyze(self, p):
        """ Returns analysis for given parameter.
        """
        param = getattr(self, p)

        if isinstance(param, (pd.DataFrame, pd.Series) ):
            return param.describe()
        else:
            module_logger.warning('Unable to analyse parameter "{0}" of type "{1}"'.format(p, type(param)))


    def mean(self, p=None ):
        """ Return mean of given parameter over given parameter. If no
        parameter is given return means vor all parameters.
        """
        if p == None:
            all_means = []
            for p in self.parameters:
                values = getattr(self, p)
                if isinstance(values, (pd.DataFrame, pd.Series)):
                    if values.ndim == 1:
                        all_means.append(values.values)
                    else:
                        all_means.append(values.mean(axis=0).values)
                else:
                    all_means.append(np.mean(values))
            return pd.DataFrame(  all_means,
                                  index=self.parameters,
                                  columns=self.objects,
                                   )
        else:
            values = getattr(self, p)
            if isinstance(values, (pd.DataFrame, pd.Series)):
                if values.ndim == 1:
                    return values
                else:
                    return values.mean(axis=0)
            else:
                return np.mean(values)


    def sanity_check(self):
        """ Does a sanity check of attached data."""
        errors_found = False

        # Test if we have the same number of frames/objects for each parameter
        shapes = [ set( getattr(self, p).shape ) for p in self.parameters ]
        intersect = shapes[0].intersection( *shapes )
        if len(intersect) > 2:
            module_logger.warning('Found varying numbers of frames: {0}'.format(intersect))
            errors_found = True

        # Test if we have the same columns labels for all parameters
        c_labels = [ set( getattr(self, p).columns ) for p in self.parameters if isinstance(getattr(self, p), pd.DataFrame) ]
        union = c_labels[0].union( *c_labels )
        if False in [ l in getattr(self, p) for p in self.parameters for l in union if isinstance(getattr(self, p), pd.DataFrame) ]:
            module_logger.warning('Found mismatches in names of objects.')
            errors_found = True

        # Test if we have any empty columns
        for p in self.parameters:
            if isinstance( getattr(self, p), pd.DataFrame ):
                if True in ( getattr(self, p).count(axis=0) == 0):
                    module_logger.warning('Found empty columns for parameter "{0}"'.format(p))
                    errors_found = True

        if not errors_found:
            module_logger.info('No errors found - all good!')


    def __getitem__(self, key):
        """ Retrieves data for a SINGLE object. Please note that for
        parameters with only a single data point per object (e.g. head_bends),
        this single parameter will be at frame 0 and the rest of the column
        will be NaN.
        """
        if key not in self.objects:
            raise ValueError('Object "{0}" not found.'.format(key))

        # Get data
        data = []
        for p in self.parameters:
            values = getattr(self, p)[key]
            if isinstance(values,float):
                values = pd.DataFrame([values])
            data.append(values)

        df = pd.concat( data, axis=1 )
        df.columns = self.parameters

        return df

    def plot_tracks(self, obj=None, ax=None, **kwargs):
        """ Plots traces of tracked objects.

        Notes
        -----
        Uses "spinepoint_2" to plot objects center.

        Parameters
        ----------
        exp :   pyFIM.Experiment
        obj :   {str, list of str, None}
                Name of object(s) to plot. If None, will plot all objects in
                Experiment.
        ax :    matplotlib.Axes, optional
                Ax to plot on. If not provided, will create a new one.
        plot :  {'center','head'}
                Which part of the object to plot.
        **kwargs
                Will be passed to ax.plot()

        Returns
        -------
        matplotlib.Axes

        """
        return fim_plot.plot_tracks(self, obj=obj,
                                          ax=ax,
                                          **kwargs)


class TwoChoiceExperiment(Experiment):
    """ Variation of :class:`~pyfim.Experiment` base class that performs
    additional analyses.
    """

    def __init__(self, f, keep_raw=False, include_subfolders=False):
        # Do everything the base class does
        super().__init__(f, keep_raw, include_subfolders)

        # Add two choice analyses
        self.two_choice_analyses()


    def two_choice_analyses(self):
        """ Performs additional two-choice analyses.
        """

        # Perform additional, "higher-level" analyses
        for param in tqdm(fim_analysis.__two_choice__, desc='Performing two-choice analyses', leave=False):
            func = getattr( fim_analysis, param )
            setattr(self, param, func( self ) )
            self.parameters.append( param )

        self.parameters = sorted( self.parameters )

    def split_data(self):
        """ Split data into experiment and control. Returns a collection.

        Notes
        -----
        You can finetune this behaviour by adjusting the following parameters in
        the config file:
            - `TC_PARAM`: parameter used to split data (e.g. "mom_x" for split along x-axis)
            - `TC_BOUNDARY`: boundary between control and experiment
            - `TC_CONTROL_SIDE`: defines which side is the control

        Please note that after splitting the data no data-clean up is performed
        before analyses are run again.

        Returns
        -------
        :class:`~pyfim.Collection` consisting of base :class:`~pyfim.Experiment`

        """

        # Get parameter by which to split data
        tc_param = getattr(self, defaults['TC_PARAM'])

        # Split data into above and below threshold
        lower_mask = tc_param <= defaults['TC_BOUNDARY']
        upper_mask = tc_param > defaults['TC_BOUNDARY']

        # Figure out which side is control
        if defaults['TC_CONTROL_SIDE'] == 0:
            ctrl_mask, exp_mask = lower_mask, upper_mask
        elif defaults['TC_CONTROL_SIDE'] == 1:
            ctrl_mask, exp_mask = upper_mask, lower_mask

        # Generate empty experiments
        experiment = Experiment(None)
        control = Experiment(None)

        # Feed original, MASKED data to each experiment
        for p in self._original_params:
            data = getattr(self, p)

            for exp, mask in zip( [experiment, control], [exp_mask, ctrl_mask] ):
                # Apply mask and drop empty columns
                masked_data = data[ mask ].dropna( axis=1, inplace=False, thresh=defaults['MIN_TRACK_LENGTH'] )
                # Apply parameter to experiment
                setattr(exp, p, masked_data)
                exp._original_params.append( p )
                exp.parameters.append( p )

        # Make sure that all objects are present in all data tables
        # -> higher level data such as "go-phase" have less data points per object and might get dropped
        for exp in [experiment, control]:
            # Get objects that are present in ALL data tables
            univ_objects = list( set.intersection(*[ set(getattr(exp, p).columns) for p in exp._original_params ]) )
            # Remove objects that are not universal
            for p in exp._original_params:
                setattr(exp, p, getattr(exp,p)[univ_objects] )

        # Rerun higher-level analyses
        for param in tqdm(fim_analysis.__all__, desc='Performing additional analyses', leave=False):
            func = getattr( fim_analysis, param )
            for exp in [experiment, control]:
                setattr(exp, param, func( exp ) )
                exp.parameters.append( param )
                exp.parameters = sorted( exp.parameters )

        col = Collection()
        col.add_data( experiment, label='experiment' )
        col.add_data( control, label='control' )

        return col


def _parse_files(x, include_subfolders=False):
    """Parses input to filenames or file objects. Will always return a list!
    """
    if isinstance(x, (np.ndarray, list, set)):
        return [ e for f in x for e in _parse_files(f) ]
    elif isinstance(x, str):
            if os.path.isfile(x):
                return [ x ]
            elif os.path.isdir(x):
                files = [ os.path.join(x,f) for f in os.listdir(x) if
                                    f.endswith(defaults['FILE_FORMAT']) ]
                if include_subfolders:
                    directories = [ os.path.join(x,f) for f in os.listdir(x) if os.path.isdir( os.path.join(x,f) ) ]
                    files += [ f for d in directories for f in _parse_files(d, True) ]

                return files
            else:
                raise ValueError('Unable to intepret "{0}" - appears to be neither a file nor a folder'.format(x))
    elif isinstance( x, IOBase ):
        return [ x ]
    else:
        raise ValueError('Unable to intepret inputs of type {0}'.format(type(x)))

