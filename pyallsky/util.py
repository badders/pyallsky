#!/usr/bin/env python

import sys
import logging

def setup_logging(level=logging.INFO, stream=sys.stdout):
    # get the default logger instance
    logger = logging.getLogger()

    # set the default output level
    logger.setLevel(level)

    # connect the logger to the requested stream
    ch = logging.StreamHandler(stream)

    # set the output format
    fmt = '%(asctime)s %(levelname)s: %(message)s'
    formatter = logging.Formatter(fmt)

    # and hook it all together
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# vim: set ts=4 sts=4 sw=4 noet tw=80:
