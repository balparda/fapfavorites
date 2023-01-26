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
"""Imagefap.com image favorites (picture folder) dowloader."""

import logging
import os
import os.path
# import pdb
import random
import re
import time
import urllib.error
import urllib.request

import click
import sanitize_filename

from baselib import base


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


# the site page templates we need
_USER_PAGE_URL = lambda n: 'https://www.imagefap.com/profile/%s' % n
_FAVS_URL = lambda u, p: 'https://www.imagefap.com/showfavorites.php?userid=%d&page=%d' % (u, p)
_FOLDER_URL = lambda u, f, p: '%s&folderid=%d' % (_FAVS_URL(u, p), f)
_IMG_URL = lambda id: 'https://www.imagefap.com/photo/%d/' % id

# the regular expressions we use to navigae the pages
_FIND_USER_ID_RE = re.compile(
    r'<a\s+class=.blk_header.\s+href="\/showfavorites.php\?userid=([0-9]+)".*>')
_FIND_ACTUAL_NAME = re.compile(r'<td\s+class=.blk_profile_hdr.*>(.*)\sProfile\s+<\/td>')
_FIND_FOLDERS_RE = re.compile(
    r'<td\s+class=.blk_favorites.><a\s+class=.blk_galleries.\s+href="'
    r'https:\/\/www.imagefap.com\/showfavorites.php\?userid=[0-9]+'
    r'&folderid=([0-9]+)".*>(.*)<\/a><\/td>')
_FAV_IMG_RE = re.compile(r'<td\s+class=.blk_favorites.\s+id="img-([0-9]+)"\s+align=')
_FULL_IMG_RE = re.compile(
    r'<img\s+id="mainPhoto".*src="(https:\/\/.*\/images\/full\/.*)">')
_IMG_NAME_RE = re.compile(
    r'<meta\s+name="description"\s+content="View this hot (.*) porn pic uploaded by')


class Error(base.Error):
  """Base GetFavorites exception."""


def _LimpingURLRead(url: str, min_wait: float = 1.0, max_wait: float = 2.0) -> bytes:
  """Read URL, but wait a semi-random time to trip up site protections.

  Args:
    url: The URL to get
    min_wait: The minimum wait, in seconds
    max_wait: The maximum wait, in seconds

  Returns:
    The bytes retrieved

  Raises:
    GFError: on error
  """
  if min_wait <= 0.0 or max_wait <= 0.0 or max_wait < min_wait:
    raise AttributeError('Invalid min/max wait times')
  tm = random.uniform(min_wait, max_wait)  # nosec
  try:
    url_data = urllib.request.urlopen(url).read()  # nosec
    logging.debug('Sleep %0.2fs...', tm)
    time.sleep(tm)
    return url_data
  except urllib.error.URLError as e:
    raise Error('Invalid URL: %s (%s)' % (url, e)) from e


def _FindID(user_name: str) -> tuple[int, str]:
  """Convert user name into user ID by invoking the user's homepage.

  Args:
    user_name: The given user name

  Returns:
    (int user ID, actual user name)

  Raises:
    Error: if conversion failed
  """
  url = _USER_PAGE_URL(user_name)
  logging.info('Fetching user page: %s', url)
  user_html = _LimpingURLRead(url).decode('utf-8')
  user_ids = _FIND_USER_ID_RE.findall(user_html)
  if len(user_ids) != 1:
    raise Error('Could not find ID for user %r' % user_name)
  uid = int(user_ids[0])
  actual_name = _FIND_ACTUAL_NAME.findall(user_html)
  if len(actual_name) != 1:
    raise Error('Could not find actual display name for user %r' % user_name)
  logging.info('User %r = ID %d', actual_name[0], uid)
  return (uid, actual_name[0])


def _FindFolder(user_id: int, favorites_name: str) -> tuple[int, str]:
  """Convert picture folder name into folder ID by finding it.

  Args:
    user_id: The user's int ID
    favorites_name: The given picture folder name

  Returns:
    (int picture folder ID, actual folder name)

  Raises:
    Error: if conversion failed
  """
  page_num = 0
  while True:
    url = _FAVS_URL(user_id, page_num)
    logging.info('Fetching favorites page: %s', url)
    fav_html = _LimpingURLRead(url).decode('utf-8')
    favs_page: list[tuple[str, str]] = _FIND_FOLDERS_RE.findall(fav_html)
    if not favs_page:
      raise Error('Could not find picture folder %r for user %d' % (favorites_name, user_id))
    for fid, fname in favs_page:
      if fname.lower() == favorites_name.lower():
        # found it!
        logging.info('Picture folder %r = ID %d', fname, int(fid))
        return (int(fid), fname)
    page_num += 1


def _ExtractFavoriteIDs(user_id: int, folder_id: int, page_num: int) -> set[int]:
  """Get numerical IDs of all images in a picture folder by URL.

  Args:
    user_id: User int ID
    folder_id: Folder int ID
    page_num: Page to request (starting on 0!)

  Returns:
    set of integer image IDs; empty set on URL error or last (empty) page
  """
  url = _FOLDER_URL(user_id, folder_id, page_num)
  logging.info('Fetching favorites page: %s', url)
  try:
    fav_html = _LimpingURLRead(url).decode('utf-8')
  except Error as e:
    logging.error('Invalid picture folder: %s', e)
    return set()
  ids = set(int(id) for id in _FAV_IMG_RE.findall(fav_html))
  logging.info('Got %d image IDs', len(ids))
  return ids


def _ExtractFullImageURL(img_id: int) -> tuple[str, str]:
  """Get URL path of the full resolution image by image ID.

  Args:
    img_id: The image numerical ID

  Returns:
    (image URL path, image name path)

  Raises:
    GFError: for invalid URLs or full-res URL not found
  """
  url = _IMG_URL(img_id)
  logging.info('Fetching image page: %s', url)
  img_html = _LimpingURLRead(url).decode('utf-8')
  full_res_urls = _FULL_IMG_RE.findall(img_html)
  if not full_res_urls:
    raise Error('No full resolution image in %s' % url)
  img_name = _IMG_NAME_RE.findall(img_html)
  if not img_name:
    raise Error('No image name path in %s' % url)
  return (full_res_urls[0], img_name[0])


def _SaveImage(url: str, name: str, dir_path: str) -> int:
  """Get an image by URL and save to directory. Will sanitize the file name if needed.

  Args:
    url: Image URL path
    name: Image (unsanitized) name
    dir_path: Local disk directory path

  Returns:
    the retrieved image bytes length

  Raises:
    GFError: for invalid URLs or empty images
  """
  logging.info('Fetching full-res image: %s', url)
  img = _LimpingURLRead(url)
  if not img:
    raise Error('Empty full-res URL: %s' % url)
  sz = len(img)
  new_name = sanitize_filename.sanitize(name)
  if new_name != name:
    logging.warning('Filename sanitization necessary %r ==> %r', name, new_name)
  full_path = os.path.join(dir_path, new_name)
  logging.info('Got %s for image %s', base.HumanizedLength(sz), full_path)
  with open(full_path, 'wb') as f:
    f.write(img)
  return sz


def _GetOperation(user_id: int, folder_id: int, output_path: str) -> None:
  """Implement `get` user operation: Straight download into a destination directory.

  Args:
    user_id: User ID
    folder_id: Folder ID
    output_path: Output path
  """
  print("Excuting GET command")
  # , so get the pages of links, until they end
  logging.info('Getting all picture folder pages and IDs')
  img_list, page_num = set(), 0
  while True:
    new_ids = _ExtractFavoriteIDs(user_id, folder_id, page_num)
    if not new_ids:
      break
    img_list = img_list.union(new_ids)
    page_num += 1
  img_list = sorted(img_list)
  logging.info('Found a total of %d unique image IDs in %d pages', len(img_list), page_num)
  # convert all the IDs into full resolution URLs
  logging.info('Getting all full resolution URLs')
  full_urls = {id: _ExtractFullImageURL(id) for id in img_list}  # {id: (url, name)}
  # dowload all full resolution images
  logging.info('Get all images and save to disk')
  total_sz = 0
  for img_id in img_list:
    total_sz += _SaveImage(*full_urls[img_id], output_path)
  # all images were downloaded, the end
  print('Saved %d images to disk (%s)' % (len(img_list), base.HumanizedLength(total_sz)))


@click.command()  # see `click` module usage in http://click.pocoo.org/
@click.argument('operation', type=click.Choice(['get']))
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
    '--output', '-o', 'output_path', type=click.STRING, default='~/Downloads/imagefap/',
    help='The intended local machine output directory path, '
         'ex: "~/somedir/"; will default to current directory')
@click.option(
    '--db/--no-db', 'make_db', default=True,
    help='Save a imagefap.database file to output? Default is yes (--db). '
         'Keeping this option on will avoid duplication of download effort.')
@base.Timed('Total Imagefap get_favorites.py execution time')
def main(operation: str,
         user_name: str,
         user_id: int,
         favorites_name: str,
         folder_id: int,
         output_path: str,
         make_db: bool) -> None:  # noqa: D301
  """Download one imagefap.com image favorites (picture folder).

  ATTENTION: The script will deliberately pace its image fetching, taking
  much longer than required to download all images. This is done so to not
  be a bad imagefap.com customer (overload their servers). Be patient! Also,
  if you leave the database option on (recommended) you will only have to
  get a folder once, as subsequent calls will ignore known images, and the
  script will detect only new arrivals.

  You have to indicate the user by either the --user or the --id options.
  You have to indicate the image favorites (picture folder) by
  either the --name or the --folder options.

  Typical examples:

  \b
  ./imagefap-favorites.py get --user "somelogin" \\
      --name "Random Images" --output "~/somedir/"
  (in this case the login/name is used and a specific output is given)

  \b
  ./imagefap-favorites.py get --id 1234 --folder 5678
  (in this case specific numerical IDs are used and
   output will be the current directory)
  """
  print('***********************************************')
  print('**   GET IMAGEFAP FAVORITES PICTURE FOLDER   **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print('***********************************************')
  success_message = 'premature end? user paused?'
  random.seed()
  try:
    # check inputs, create output directory if needed
    if not user_name and not user_id:
      raise AttributeError('You have to provide either the --user or the --id options')
    if not favorites_name and not folder_id:
      raise AttributeError('You have to provide either the --name or the --folder options')
    output_path_expanded = os.path.expanduser(output_path)
    if os.path.isdir(output_path_expanded):
      logging.info('Output directory %r already exists', output_path)
    else:
      logging.info('Creating output directory %r', output_path)
      os.mkdir(output_path_expanded)
    # convert user to id and convert name to folder, if needed
    if not user_id:
      user_id = _FindID(user_name)[0]
    if not folder_id:
      folder_id = _FindFolder(user_id, favorites_name)[0]
    # we should now have both IDs that we need
    if operation.lower() == 'get':
      _GetOperation(user_id, folder_id, output_path_expanded)
    else:
      raise NotImplementedError('Unrecognized/Unimplemented operation %r' % operation)
    success_message = 'success'
  except Exception as e:
    success_message = 'error: ' + str(e)
    raise
  finally:
    print('THE END: ' + success_message)


if __name__ == '__main__':
  main()  # pylint: disable=no-value-for-parameter
