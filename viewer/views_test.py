#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""views.py unittest."""

import os
# import pdb
from typing import Any
import unittest
from unittest import mock

# import duplicates
# import fapdata

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

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.os.path.getsize')
  def test_ServeIndex(self, mock_getsize, mock_render, mock_db):
    """Test."""
    mock_db.return_value = _TestDBFactory()
    mock_getsize.return_value = 100000
    views.ServeIndex('req')  # type: ignore
    mock_render.assert_called_once_with('req', 'viewer/index.html', _INDEX_CONTEXT)


@mock.patch('fapdata.os.path.isdir')
def _TestDBFactory(mock_isdir) -> views.fapdata.FapDatabase:
  mock_isdir.return_value = True
  db = views.fapdata.FapDatabase('/foo/', create_if_needed=False)
  db._db = _MOCK_DATABASE
  db.duplicates = views.duplicates.Duplicates(db._duplicates_registry, db._duplicates_key_index)
  return db


_MOCK_DATABASE: views.fapdata._DatabaseType = {
    'users': {
    },
    'favorites': {
    },
    'tags': {
    },
    'blobs': {
    },
    'image_ids_index': {
    },
    'duplicates_registry': {
    },
    'duplicates_key_index': {
    },
}

_INDEX_CONTEXT: dict[str, Any] = {
    'users': 0,
    'tags': 0,
    'duplicates': 0,
    'dup_action': 0,
    'n_images': 0,
    'database_stats': [
        ("Database is located in '/foo/imagefap.database', and is 97.66kb "
         "(10000000.00000% of total images size)"),
        ('0b total (unique) images size '
         '(- min, - max, - mean with - standard deviation, 0 are animated)'),
        '',
        '0 users',
        '0 favorite galleries (oldest: pending / newer: pending)',
        '0 unique images (0 total, 0 exact duplicates)', '0 perceptual duplicates in 0 groups',
    ],
}


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestDjangoViews)


if __name__ == '__main__':
  unittest.main()
