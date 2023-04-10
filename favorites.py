#!/usr/bin/python3 -O
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License 3 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see http://www.gnu.org/licenses/gpl-3.0.txt.
#
"""Imagefap.com image favorites (picture folder) downloader."""

import logging
# import pdb

import click

from baselib import base
from fapfavorites import fapdata


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


def _GetOperation(
    user_id: int, user_name: str, folder_id: int, favorites_name: str, output_path: str) -> None:
  """Implement `get` user operation: Straight download into a destination directory.

  Args:
    user_id: User ID
    user_name: User name
    folder_id: Folder ID
    favorites_name: Folder name
    output_path: Output path to use
  """
  print('Executing GET command')
  user_id = user_id if user_id else fapdata.ConvertUserName(user_name)
  fapdata.DownloadFavorites(
      user_id,
      folder_id if folder_id else fapdata.ConvertFavoritesName(user_id, favorites_name)[0],
      output_path)


def _ReadOperation(database: fapdata.FapDatabase,
                   user_id: int,
                   folder_id: int,
                   force_download: bool) -> None:
  """Implement `read` user operation: Read into database either one or all favorites.

  Args:
    database: Active fapdata.FapDatabase
    user_id: User ID
    folder_id: Folder ID
    force_download: If True will download even if recently downloaded
  """
  # start
  print('Executing READ command')
  found_folder_ids: set[int] = ({folder_id} if folder_id else
                                database.AddAllUserFolders(user_id, force_download))
  total_sz: int = 0
  for f_id in sorted(found_folder_ids):
    database.AddFolderPics(user_id, f_id, force_download)
    total_sz += database.DownloadAll(user_id, f_id, fapdata.CHECKPOINT_LENGTH, force_download)
  # if we finished getting all user albums, mark user as finished
  if not folder_id:
    # use lazy users.get() so tests don't have to mock the actual DB
    database.users.get(user_id, {})['date_finished'] = base.INT_TIME()
  # find perceptual duplicates
  if total_sz:
    database.FindDuplicates()
  # save DB, if we need to
  if total_sz or not folder_id:
    database.Save()
  logging.info('Downloaded a total of: %s', base.HumanizedBytes(total_sz))


def _AuditOperation(database: fapdata.FapDatabase, user_id: int, force_audit: bool) -> None:
  """Implement `audit` user operation: Check all user images for continued existence.

  Args:
    database: Active fapdata.FapDatabase
    user_id: User ID
    force_audit: If True will audit even if recently audited
  """
  # start
  print('Executing AUDIT command')
  database.Audit(user_id, fapdata.AUDIT_CHECKPOINT_LENGTH, force_audit)
  database.Save()


@click.command()  # see `click` module usage in http://click.pocoo.org/
@click.argument('operation', type=click.Choice(['get', 'read', 'audit']))
@click.option(
    '--user', '-u', 'user_name', type=click.STRING, default='',
    help='The imagefap.com user name, as found in https://www.imagefap.com/profile/USER; '
         'we can\'t yet properly deal with HTML escaping names, so be aware of this')
@click.option(
    '--id', '-i', 'user_id', type=click.INT, default=0,
    help='The imagefap.com user ID, as found in '
         'https://www.imagefap.com/showfavorites.php?userid=ID&folderid=FOLDER')
@click.option(
    '--name', '-n', 'favorites_name', type=click.STRING, default='',
    help='The user\'s image favorites (picture folder) name, ex: "Random Images"; '
         'we can\'t yet properly deal with HTML escaping names, so be aware of this')
@click.option(
    '--folder', '-f', 'folder_id', type=click.INT, default=0,
    help='The imagefap.com folder ID, as found in '
         'https://www.imagefap.com/showfavorites.php?userid=ID&folderid=FOLDER')
@click.option(
    '--output', '-o', 'output_path', type=click.STRING, default=fapdata.DEFAULT_DB_DIRECTORY,
    help='The intended local machine output directory path, '
         f'ex: "~/some-dir/"; will default to {fapdata.DEFAULT_DB_DIRECTORY!r}')
@click.option(
    '--force/--no-force', 'force_download', default=False,
    help='Ignore recency check for download/audit of favorite images? Default '
         'is False ("no"). This will force a download/audit even if the album/image '
         'is fresh in the database')
@base.Timed('Total Imagefap favorites.py execution time')
def Main(operation: str,  # noqa: C901
         user_name: str,
         user_id: int,
         favorites_name: str,
         folder_id: int,
         output_path: str,
         force_download: bool) -> None:  # noqa: D301
  """Download imagefap.com image favorites (picture folder).

  ATTENTION: The script will deliberately pace its image fetching, taking
  much longer than required to download all images. This is done so to not
  be a bad imagefap.com customer (overload their servers). Be patient! If
  you are reading (`read` operation) into a database (recommended) you will
  only have to get a folder once, as subsequent calls will ignore known images,
  and the script will detect new arrivals. A big time saver.

  You have to indicate the user by either the --user or the --id options.
  You have to indicate the image favorites (picture folder) by
  either the --name or the --folder options if you are using `get`.
  If you are using `read` then you can specify only the user and
  let it browse for all image favorite galleries automatically.

  After you have a database in place you can use the `audit` operation to
  look at all pictures for a --user (or --id) and find out if any images
  in the DB are missing from the site. This will *not* download any new images
  but will re-check the existence of images in the database for that user.
  Use `audit` sparingly, as it is rather wasteful.

  Typical examples:

  \b
  ./favorites.py get --user "some-login" \\
      --name "Random Images" --output "~/some-dir/"
  (in this case the login/name is used and a specific output is given;
   all images are saved to "~/some-dir/" with their original names;
   no database is created and no automation happens, just straight fetch)

  \b
  ./favorites.py read --user "some-login"
  (in this case, will find all image favorite galleries for this user
   and place them in the database; if this is a known user no duplicate
   work will be done)

  \b
  ./favorites.py audit --user "some-login" --force
  (will look at all the images this user has and check if they exist
   but will not download any new image; will ignore recent audits)
  """
  print('**************************************************')
  print('**   GET IMAGEFAP FAVORITES PICTURE FOLDER(s)   **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print('***********************************************')
  success_message: str = 'premature end? user paused?'
  try:
    # check inputs
    if not user_name and not user_id:
      raise AttributeError('You have to provide either the --user or the --id options')
    if user_name and user_id:
      raise AttributeError('You should not provide both the --user and the --id options')
    if favorites_name and folder_id:
      raise AttributeError('You should not provide both the --name and the --folder options')
    if (not favorites_name and not folder_id) and operation.lower() not in {'read', 'audit'}:
      raise AttributeError('You have to provide either the --name or the --folder options')
    if (favorites_name or folder_id) and operation.lower() == 'audit':
      raise AttributeError('You should not provide --name or --folder in the `audit` operation')
    # Tackle `get` operation first: na database to load or save
    if operation.lower() == 'get':
      _GetOperation(user_id, user_name, folder_id, favorites_name, output_path)
      success_message = 'success'
      return
    # the other operations need a database and adding user/folder to it first
    database = fapdata.FapDatabase(output_path)
    database.Load()
    # convert user to id and convert name to folder, if needed
    if user_id:
      database.AddUserByID(user_id)
    else:
      user_id = database.AddUserByName(user_name)[0]
    if folder_id:
      database.AddFolderByID(user_id, folder_id)
    else:
      if favorites_name:
        folder_id = database.AddFolderByName(user_id, favorites_name)[0]
    # we should now have both IDs that we need for the database operations
    if operation.lower() == 'read':
      _ReadOperation(database, user_id, folder_id, force_download)
    elif operation.lower() == 'audit':
      _AuditOperation(database, user_id, force_download)
    else:
      raise NotImplementedError(f'Unrecognized/Unimplemented operation {operation!r}')
    success_message = 'success'
  except Exception as err:
    success_message = f'error: {err}'
    raise
  finally:
    print('THE END: ' + success_message)


if __name__ == '__main__':
  Main()  # pylint: disable=no-value-for-parameter
