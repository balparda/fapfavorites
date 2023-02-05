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
import django
from django.core.management import execute_from_command_line as django_execute
# from django.core.management import call_command as django_call

from baselib import base
import fapdata


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


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


def _RunDjangoServerAndBlock(database: fapdata.FapDatabase) -> None:
  """Run the main Django server and block on call until server comes down.

  Args:
    database: Active fapdata.FapDatabase
  """
  # for sha in database.blobs.keys():
  #   database._MakeThumbnailForBlob(sha)
  # return
  logging.info('Starting Django local server')
  # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fapper.settings')  # cspell:disable-line
  # django.setup()
  django_execute(['foo', 'runserver'])
  # django_call('runserver')


@click.command()  # see `click` module usage in http://click.pocoo.org/
@click.argument('operation', type=click.Choice(['stats', 'print', 'run']))
@click.option(
    '--dir', '-d', 'db_dir', type=click.STRING, default=fapdata.DEFAULT_DB_DIRECTORY,
    help='The local machine database directory path to use, '
         'ex: "~/some-dir/"; will default to %r' % fapdata.DEFAULT_DB_DIRECTORY)
@click.option(
    '--blobs/--no-blobs', 'print_blobs', default=False,
    help='Print all blobs in `print` command? Default is False ("no")')
@base.Timed('Total Imagefap process.py execution time')
def main(operation: str, db_dir: str, print_blobs: bool) -> None:  # noqa: D301
  """imagefap.com database operations utility.

  This is intended to be used on a database that has been constructed
  by reading imagefap.com data. To construct a database, use the `read`
  command of the `favorites.py` utility.

  The `stats` command prints interesting info on the database's metadata.

  The `print` command will do a "pretty" print of useful database metadata
  for a closer inspection. Can print a lot for a big database!

  Typical examples:

  \b
  ./process.py stats --dir "~/some-dir/"
  (print statistics for database in "~/some-dir/")

  \b
  ./process.py print
  (pretty-print useful data from the default database location)
  """
  print('***********************************************')
  print('**    IMAGEFAP DATABASE PROCESSING UTILS     **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print('***********************************************')
  success_message = 'premature end? user paused?'
  try:
    # load database
    database = fapdata.FapDatabase(db_dir, create_if_needed=False)
    if not database.Load():
      raise fapdata.Error('Database does not exist in given path: %r' % db_dir)
    if not database.blobs_dir_exists:
      raise fapdata.Error('Database blobs directory does not inside %r' % db_dir)
    # we should now have both IDs that we need
    if operation.lower() == 'stats':
      _StatsOperation(database)
    elif operation.lower() == 'print':
      _PrintOperation(database, print_blobs)
    elif operation.lower() == 'run':
      _RunDjangoServerAndBlock(database)
    else:
      raise NotImplementedError('Unrecognized/Unimplemented operation %r' % operation)
    # for now, no operation needs to save DB
    # database.Save()
    success_message = 'success'
  except Exception as e:
    success_message = 'error: ' + str(e)
    raise
  finally:
    print('THE END: ' + success_message)


if __name__ == '__main__':
  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fapper.settings')  # cspell:disable-line
  django.setup()
  main()  # pylint: disable=no-value-for-parameter
