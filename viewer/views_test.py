#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""views.py unittest."""

import os
# import pdb
import unittest
# from unittest import mock

os.environ['DJANGO_SETTINGS_MODULE'] = 'fapper.settings'  # cspell:disable-line
from viewer import views  # noqa: E402

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestDjangoViews(unittest.TestCase):
  """Tests for views.py."""

  def test_SHA256HexDigest(self):
    """Test."""
    digest = views.SHA256HexDigest()
    self.assertEqual(digest.to_python('fOO'), 'foo')
    self.assertEqual(digest.to_url('Bar'), 'bar')


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestDjangoViews)


if __name__ == '__main__':
  unittest.main()
