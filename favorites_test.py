#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""favorites.py unittest."""

# import pdb
import unittest
from unittest import mock

import favorites

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestFavorites(unittest.TestCase):
  """Tests for favorites.py."""

  @mock.patch('favorites.fapdata.os.path.isdir')
  @mock.patch('favorites.fapdata.FapDatabase.Load')
  @mock.patch('favorites.fapdata.FapDatabase.Save')
  @mock.patch('favorites.fapdata.FapDatabase.AddUserByID')
  @mock.patch('favorites.fapdata.FapDatabase.AddUserByName')
  @mock.patch('favorites.fapdata.FapDatabase.AddFolderByID')
  @mock.patch('favorites.fapdata.FapDatabase.AddFolderByName')
  @mock.patch('favorites.fapdata.FapDatabase.AddFolderPics')
  @mock.patch('favorites.fapdata.FapDatabase.DownloadFavorites')
  @mock.patch('favorites.fapdata.FapDatabase.ReadFavoritesIntoBlobs')
  @mock.patch('favorites.fapdata.FapDatabase.FindDuplicates')
  @mock.patch('favorites.fapdata.FapDatabase.AddAllUserFolders')
  def test_GetOperation(
      self, add_all, find_duplicates, read_favorites, download_favorites, add_folder_pics,
      add_folder_by_name, add_folder_by_id, add_user_by_name, add_user_by_id,
      save, load, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    try:
      favorites.main(['get', '--id', '10', '--folder', '20', '--output', '/path/', '--no-db'])
    except SystemExit as e:
      if e.code:
        raise
    mock_is_dir.assert_called_with('/path/')
    load.assert_not_called()
    add_user_by_id.assert_called_with(10)
    add_user_by_name.assert_not_called()
    add_folder_by_id.assert_called_with(10, 20)
    add_folder_by_name.assert_not_called()
    add_folder_pics.assert_called_with(10, 20, False)
    download_favorites.assert_called_with(10, 20, 0, False)
    save.assert_not_called()
    read_favorites.assert_not_called()
    find_duplicates.assert_not_called()
    add_all.assert_not_called()

  @mock.patch('favorites.fapdata.os.path.isdir')
  @mock.patch('favorites.fapdata.FapDatabase.Load')
  @mock.patch('favorites.fapdata.FapDatabase.Save')
  @mock.patch('favorites.fapdata.FapDatabase.AddUserByID')
  @mock.patch('favorites.fapdata.FapDatabase.AddUserByName')
  @mock.patch('favorites.fapdata.FapDatabase.AddFolderByID')
  @mock.patch('favorites.fapdata.FapDatabase.AddFolderByName')
  @mock.patch('favorites.fapdata.FapDatabase.AddFolderPics')
  @mock.patch('favorites.fapdata.FapDatabase.DownloadFavorites')
  @mock.patch('favorites.fapdata.FapDatabase.ReadFavoritesIntoBlobs')
  @mock.patch('favorites.fapdata.FapDatabase.FindDuplicates')
  @mock.patch('favorites.fapdata.FapDatabase.AddAllUserFolders')
  def test_ReadOperation(
      self, add_all, find_duplicates, read_favorites, download_favorites, add_folder_pics,
      add_folder_by_name, add_folder_by_id, add_user_by_name, add_user_by_id,
      save, load, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    add_user_by_name.return_value = (10, 'some-user')
    add_folder_by_name.return_value = (20, 'some-folder')
    add_all.return_value = {100, 200}
    try:
      favorites.main(['read', '--user', '"foo-user"', '--output', '/path/', '--force'])
    except SystemExit as e:
      if e.code:
        raise
    mock_is_dir.assert_called_with('/path/')
    load.assert_called_with()
    add_user_by_id.assert_not_called()
    add_user_by_name.assert_called_with('"foo-user"')
    add_folder_by_id.assert_not_called()
    add_folder_by_name.assert_not_called()
    self.assertListEqual(
        add_folder_pics.call_args_list, [mock.call(10, 100, True), mock.call(10, 200, True)])
    self.assertListEqual(
        read_favorites.call_args_list, [mock.call(10, 100, 10, True), mock.call(10, 200, 10, True)])
    find_duplicates.assert_called_with()
    save.assert_called_with()
    download_favorites.assert_not_called()


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFavorites)


if __name__ == '__main__':
  unittest.main()
