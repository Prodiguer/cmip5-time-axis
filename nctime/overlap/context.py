#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    :platform: Unix
    :synopsis: Processing context used in this module.

"""
import sys
from multiprocessing.managers import BaseManager

from ESGConfigParser import SectionParser

from handler import Graph
from nctime.utils.collector import Collector
from nctime.utils.constants import *
from nctime.utils.custom_exceptions import InvalidFrequency
from nctime.utils.time import TimeInit

BaseManager.register('graph', Graph, exposed=('get_graph',
                                              'has_graph',
                                              'set_graph',
                                              'add_node',
                                              'add_edge',
                                              '__call__'))


class ProcessManager(BaseManager):
    pass


class ProcessingContext(object):
    """
    Encapsulates the processing context/information for main process.

    :param ArgumentParser args: Parsed command-line arguments
    :returns: The processing context
    :rtype: *ProcessingContext*

    """

    def __init__(self, args):
        self.directory = args.directory
        self.config_dir = args.i
        self.resolve = args.resolve
        self.full_overlap_only = args.full_overlap_only
        self.project = args.project
        if args.set_inc:
            for frequency, increment in dict(args.set_inc).items():
                if frequency not in FREQ_INC.keys():
                    raise InvalidFrequency(frequency)
                FREQ_INC[frequency][0] = int(increment)
        self.tunits_default = None
        self.true_dates = args.true_dates
        self.processes = args.max_processes
        self.use_pool = (self.processes != 1)
        if self.project in DEFAULT_TIME_UNITS.keys():
            self.tunits_default = DEFAULT_TIME_UNITS[self.project]
        self.overlaps = 0
        self.broken = 0
        self.scan_files = 0
        self.scan_dsets = 0
        self.pbar = None
        self.file_filter = []
        if args.include_file:
            self.file_filter.extend([(f, True) for f in args.include_file])
        else:
            # Default includes netCDF only
            self.file_filter.append(('^.*\.nc$', True))
        if args.exclude_file:
            # Default exclude hidden files
            self.file_filter.extend([(f, False) for f in args.exclude_file])
        else:
            self.file_filter.append(('^\..*$', False))
        self.dir_filter = args.ignore_dir

    def __enter__(self):
        # Init configuration parser
        self.cfg = SectionParser(section='project:{}'.format(self.project), directory=self.config_dir)
        self.pattern = self.cfg.translate('filename_format')
        # Init data collector
        self.sources = Collector(sources=self.directory)
        # Init file filter
        for regex, inclusive in self.file_filter:
            self.sources.FileFilter.add(regex=regex, inclusive=inclusive)
        # Exclude fixed frequency in any case
        self.sources.FileFilter.add(regex='(_fx_|_fixed_|_fx.|_fixed.|_.fx_)', inclusive=False)
        # Init dir filter
        self.sources.PathFilter.add(regex=self.dir_filter, inclusive=False)
        # Set driving time properties
        self.tinit = TimeInit(ref=self.sources.first(), tunits_default=self.tunits_default)
        self.ref_calendar = self.tinit.calendar
        return self

    def __exit__(self, *exc):
        # Decline outputs depending on the scan results
        print('Number of files scanned: {}'.format(self.scan_files))
        print('Number of datasets: {}'.format(self.scan_dsets))
        print('Number of datasets with error(s): {}'.format(self.broken + self.overlaps))
        if self.broken:
            sys.exit(1)
        elif self.overlaps:
            sys.exit(2)
        else:
            sys.exit(0)
