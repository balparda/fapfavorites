#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""Run all the tests so we can have easy global coverage."""

import logging

from baselib import base
import fapdata_test

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


@base.Timed('Total imagefap-favorites package test time')
def main():
  """Run all of the tests."""
  logging.warning('*' * 80)
  logging.warning('Running fapdata.py tests')
  fapdata_test.SUITE.debug()
  logging.info('OK')
  logging.warning('*' * 80)
  return 0


if __name__ == "__main__":
  main()
