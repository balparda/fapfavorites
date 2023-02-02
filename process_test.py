#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""process.py unittest."""

# import pdb
import unittest
# from unittest import mock

# import favorites

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestProcess(unittest.TestCase):
  """Tests for process.py."""

  def test_TODO(self):
    """Test."""
    # TODO: write a test


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestProcess)


if __name__ == '__main__':
  unittest.main()
