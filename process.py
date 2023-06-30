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
"""Imagefap.com image database operations."""

import logging
import os
# import pdb

import click
from django.core import management

from baselib import base
from fapfavorites import fapdata


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (2, 0)


def _StatsOperation(database: fapdata.FapDatabase) -> None:
  """Implement `stats` user operation: Print statistics.

  Args:
    database: Active fapdata.FapDatabase
  """
  print('Executing STATS command')
  print()
  print()
  database.PrintStats()
  print()
  print()


def _PrintOperation(database: fapdata.FapDatabase, print_blobs: bool) -> None:
  """Implement `print` user operation: Print statistics.

  Args:
    database: Active fapdata.FapDatabase
    print_blobs: Print blobs?
  """
  print('Executing PRINT command')
  print()
  print()
  print('=' * 80)
  print('=' * 80)
  print()
  print('                             **** USERS & FAVORITES ****')
  print()
  database.PrintUsersAndFavorites()
  print()
  print('=' * 80)
  print()
  print('                             **** TAGS ****')
  print()
  database.PrintTags()
  print()
  if print_blobs:
    print('=' * 80)
    print()
    print('                             **** IMAGE BLOBS METADATA ****')
    print()
    database.PrintBlobs()
    print()
  print('=' * 80)
  print()
  database.PrintStats()
  print()
  print('=' * 80)
  print('=' * 80)
  print()
  print()


def _RunDjangoServerAndBlock(development_mode: bool) -> None:
  """Run the main Django server and block on call until server comes down.

  Args:
    database: Active fapdata.FapDatabase
  """
  logging.info('Starting Django local server in %s mode',
               'DEVELOPMENT' if development_mode else 'USER')
  argv: list[str] = ['./process.py', 'runserver']
  if not development_mode:
    # this will disable the Django auto-reload BUT will make everything in process.py load TWICE
    argv.append('--noreload')  # cspell:disable-line
  print('Executing RUN command, server in: '
        f'{base.TERM_MAGENTA}{base.TERM_BOLD}{base.TERM_UNDERLINE}'
        f'http://127.0.0.1:8000/viewer/{base.TERM_END}')
  management.execute_from_command_line(argv)


def _RunExport(database: fapdata.FapDatabase, tag_name: str, renumber_files: bool) -> None:
  """Implement `export` user operation: save tagged images to disk.

  Args:
    database: Active fapdata.FapDatabase
    tag_name: Tag name to export; may be empty, meaning all tags will be exported
    renumber_files: Should be re-number the files?
  """
  print('Executing EXPORT command')
  tag_name = tag_name.strip()
  if not tag_name:
    database.ExportAll(re_number_files=renumber_files)
    return
  for tid, name, _, _ in database.TagsWalk():
    if tag_name.lower() == name.lower():
      database.ExportTag(tid, re_number_files=renumber_files)
      break
  else:
    raise fapdata.Error('Tag f{tag_name!r} not found in database')


@click.command()  # see `click` module usage in http://click.pocoo.org/
@click.argument('operation', type=click.Choice(['stats', 'print', 'run', 'export']))
@click.option(
    '--dir', '-d', 'db_dir', type=click.STRING, default=fapdata.DEFAULT_DB_DIRECTORY,
    help='The local machine database directory path to use, '
         f'ex: "~/some-dir/"; will default to {fapdata.DEFAULT_DB_DIRECTORY!r}')
@click.option(
    '--tag', '-t', 'tag_name', type=click.STRING, default='',
    help='The tag name to export for `export` command, ex: "Favorites"')
@click.option(
    '--renumber/--no-renumber', 'renumber_files', default=False,
    help='Preserve file order by renumbering the file names? Default is False ("no")')
@click.option(
    '--blobs/--no-blobs', 'print_blobs', default=False,
    help='Print all blobs in `print` command? Default is False ("no")')
@click.option(
    '--development/--no-development', 'development_mode', default=False,
    help='Open web app `run` command in development mode? Default is False ("no"); '
         'usually you\'ll want to keep this off, which is the default, but if you are '
         'developing it is useful as Django will reload automatically when you change some '
         'resource, but the drawback (and the reason for the default) is that the app will '
         'initially load twice, taking more time to start')
@base.Timed('Total Imagefap process.py execution time')
def Main(operation: str,
         db_dir: str,
         tag_name: str,
         renumber_files: bool,
         print_blobs: bool,
         development_mode: bool) -> None:  # noqa: D301
  """imagefap.com database operations utility.

  This is intended to be used on a database that has been constructed
  by reading imagefap.com data. To construct a database, use the `read`
  command of the `favorites.py` utility.

  The `stats` command prints interesting info on the database's metadata.

  The `print` command will do a "pretty" print of useful database metadata
  for a closer inspection. Can print a lot for a big database!

  The `run` command will start a strictly local web app with the database
  data that will allow you to navigate and view the data and do some tasks.
  Web app will be in http://127.0.0.1:8000/viewer/

  The `export` command will export tagged images to disk. The files will be
  located in the `/tag_export/` subdirectory of the database location, in
  sub-directories that reflect the tag names and structure. The files will
  use the original name, if available, and will be *unencrypted*! You also
  have a `--renumber` flag that will add a numerical prefix in the files
  and so guarantee the file ordering.Note that, if an image has more than
  one tag, it will be exported to multiple locations.

  Typical examples:

  \b
  ./process.py stats --dir "~/some-dir/"
  (print statistics for database in "~/some-dir/")

  \b
  ./process.py print
  (pretty-print useful data from the default database location)

  \b
  ./process.py run
  (run local web app in http://127.0.0.1:8000/viewer/)

  \b
  ./process.py export --tag "Favorites"
  (export all images that were tagged "Favorites"
   to "~/Downloads/imagefap/tag_export/[...]/Favorites/")
  """
  print(f'{base.TERM_BLUE}{base.TERM_BOLD}***********************************************')
  print('**    IMAGEFAP DATABASE PROCESSING UTILS     **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print(f'***********************************************{base.TERM_END}')
  success_message: str = f'{base.TERM_WARNING}premature end? user paused?'
  try:
    # load database
    database = fapdata.FapDatabase(db_dir, create_if_needed=False)
    if operation.lower() != 'run':
      if not database.Load():
        raise fapdata.Error(f'Database does not exist in given path: {db_dir!r}')
    # we should now have both IDs that we need
    if operation.lower() == 'stats':
      _StatsOperation(database)
    elif operation.lower() == 'print':
      _PrintOperation(database, print_blobs)
    elif operation.lower() == 'run':
      _RunDjangoServerAndBlock(development_mode)
    elif operation.lower() == 'export':
      _RunExport(database, tag_name, renumber_files)
    else:
      raise NotImplementedError(f'Unrecognized/Unimplemented operation {operation!r}')
    # for now, no operation needs to save DB
    # database.Save()
    success_message = f'{base.TERM_GREEN}success'
  except Exception as err:
    success_message = f'{base.TERM_FAIL}error: {err}'
    raise
  finally:
    print(f'{base.TERM_BLUE}{base.TERM_BOLD}THE END: {success_message}{base.TERM_END}')


if __name__ == '__main__':
  os.environ['DJANGO_SETTINGS_MODULE'] = 'fapper.settings'  # cspell:disable-line
  Main()  # pylint: disable=no-value-for-parameter
