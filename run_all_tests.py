#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""Run all the tests so we can have easy global coverage."""

import logging

from baselib import base
from fapfavorites import fapbase_test
from fapfavorites import duplicates_test
from fapfavorites import fapdata_test
from fapfavorites import favorites_test
from fapfavorites import process_test
from fapfavorites.viewer import views_test

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TEST_MODULES_TO_RUN = (
    fapbase_test,
    duplicates_test,
    fapdata_test,
    favorites_test,
    process_test,
    views_test,
)


@base.Timed('fapfavorites tests')
def Main() -> int:
  """Run all of the tests."""
  logging.info('*' * 80)
  for module in _TEST_MODULES_TO_RUN:
    logging.info('Running tests: %s.py', module.__name__)
    module.SUITE.debug()
    logging.info('OK')
    logging.info('*' * 80)
  logging.info('               ======>>>>  ALL MODULES PASSED OK  <<<<======')
  logging.info('*' * 80)
  return 0


if __name__ == "__main__":
  Main()
