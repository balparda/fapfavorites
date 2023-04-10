#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# pylint: disable=invalid-name,protected-access
"""process.py unittest."""

# import pdb
import unittest
from unittest import mock

from fapfavorites import process

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestProcess(unittest.TestCase):
  """Tests for process.py."""

  @mock.patch('fapfavorites.process.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.Load')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.Save')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.PrintStats')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.PrintUsersAndFavorites')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.PrintTags')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.PrintBlobs')
  def test_StatsOperation(
      self, print_blobs: mock.MagicMock, print_tags: mock.MagicMock, print_users: mock.MagicMock,
      print_stats: mock.MagicMock, save: mock.MagicMock, load: mock.MagicMock,
      mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    try:
      process.Main(['stats', '--dir', '/path/'])  # pylint: disable=no-value-for-parameter
    except SystemExit as e:
      if e.code:  # pylint: disable=using-constant-test
        raise
    self.assertListEqual(
        mock_is_dir.call_args_list,
        [mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/'),
         mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/'),
         mock.call('/path/blobs/')])
    load.assert_called_once_with()
    print_stats.assert_called_once_with()
    save.assert_not_called()
    print_blobs.assert_not_called()
    print_tags.assert_not_called()
    print_users.assert_not_called()

  @mock.patch('fapfavorites.process.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.Load')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.Save')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.PrintStats')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.PrintUsersAndFavorites')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.PrintTags')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.PrintBlobs')
  def test_PrintOperation(
      self, print_blobs: mock.MagicMock, print_tags: mock.MagicMock, print_users: mock.MagicMock,
      print_stats: mock.MagicMock, save: mock.MagicMock, load: mock.MagicMock,
      mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    try:
      process.Main(  # pylint: disable=no-value-for-parameter
          ['print', '--dir', '/path/', '--blobs'])
    except SystemExit as e:
      if e.code:  # pylint: disable=using-constant-test
        raise
    self.assertListEqual(
        mock_is_dir.call_args_list,
        [mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/'),
         mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/'),
         mock.call('/path/blobs/')])
    load.assert_called_once_with()
    print_users.assert_called_once_with()
    print_tags.assert_called_once_with()
    print_blobs.assert_called_once_with()
    print_stats.assert_called_once_with()
    save.assert_not_called()

  @mock.patch('fapfavorites.process.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.Load')
  @mock.patch('fapfavorites.process.fapdata.FapDatabase.Save')
  @mock.patch('django.core.management.execute_from_command_line')
  def test_RunOperation(
      self, mock_django: mock.MagicMock, save: mock.MagicMock, load: mock.MagicMock,
      mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    try:
      process.Main(['run', '--dir', '/path/'])  # pylint: disable=no-value-for-parameter
    except SystemExit as e:
      if e.code:  # pylint: disable=using-constant-test
        raise
    self.assertListEqual(
        mock_is_dir.call_args_list,
        [mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/'),
         mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/')])
    mock_django.assert_called_once_with(
        ['./process.py', 'runserver', '--noreload'])  # cspell:disable-line
    load.assert_not_called()
    save.assert_not_called()


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestProcess)


if __name__ == '__main__':
  unittest.main()
