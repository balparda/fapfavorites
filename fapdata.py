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
"""Imagefap.com database."""

import hashlib
import logging
import os
import os.path
# import pdb
import random
import re
import time
import urllib.error
import urllib.request

import sanitize_filename

from baselib import base


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_DB_MAIN_KEYS = {
    'users',
    'favorites',
    'tags',
    'blobs',
    'imageidsidx',
}

# the site page templates we need
_USER_PAGE_URL = lambda n: 'https://www.imagefap.com/profile/%s' % n
_FAVS_URL = lambda u, p: 'https://www.imagefap.com/showfavorites.php?userid=%d&page=%d' % (u, p)
_FOLDER_URL = lambda u, f, p: '%s&folderid=%d' % (_FAVS_URL(u, p), f)
_IMG_URL = lambda id: 'https://www.imagefap.com/photo/%d/' % id

# the regular expressions we use to navigate the pages
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
  """Base fap exception."""


def LimpingURLRead(url: str, min_wait: float = 1.0, max_wait: float = 2.0) -> bytes:
  """Read URL, but wait a semi-random time to trip up site protections.

  Args:
    url: The URL to get
    min_wait: (default 1.0) The minimum wait, in seconds
    max_wait: (default 2.0) The maximum wait, in seconds

  Returns:
    The bytes retrieved

  Raises:
    Error: on error
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


class FapDatabase():
  """Imagefap.com database."""

  def __init__(self):
    """Construct a clean database."""
    # start with a clean DB; see README.md for format
    self._db: dict[str, dict] = {}
    for k in _DB_MAIN_KEYS:  # creates the main expected key entries
      self._db[k] = {}

  def Load(self, path: str) -> None:
    """Load DB from file.

    Args:
      path: The file path to load DB from

    Raises:
      Error: if found DB does not check out
    """
    if os.path.exists(path):
      self._db = base.BinDeSerialize(file_path=path)
      # just a quick dirty check that we got what we expected
      if any(k not in self._db for k in _DB_MAIN_KEYS):
        raise Error('Loaded DB is invalid!')
      logging.info('Loaded DB from %r', path)
    else:
      logging.warning('No DB found in %r', path)

  def Save(self, path: str) -> None:
    """Save DB to file.

    Args:
      path: The file path to save DB to
    """
    base.BinSerialize(self._db, path)
    logging.info('Saved DB to %r', path)

  def AddUserByName(self, user_name: str) -> tuple[int, str]:
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
    user_html = LimpingURLRead(url).decode('utf-8')
    user_ids = _FIND_USER_ID_RE.findall(user_html)
    if len(user_ids) != 1:
      raise Error('Could not find ID for user %r' % user_name)
    uid = int(user_ids[0])
    actual_name = _FIND_ACTUAL_NAME.findall(user_html)
    if len(actual_name) != 1:
      raise Error('Could not find actual display name for user %r' % user_name)
    logging.info('User %r = ID %d', actual_name[0], uid)
    self._db['users'][uid] = actual_name[0]
    return (uid, actual_name[0])

  def AddFolderByName(self, user_id: int, favorites_name: str) -> tuple[int, str]:
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
      fav_html = LimpingURLRead(url).decode('utf-8')
      favs_page: list[tuple[str, str]] = _FIND_FOLDERS_RE.findall(fav_html)
      if not favs_page:
        raise Error('Could not find picture folder %r for user %d' % (favorites_name, user_id))
      for fid, fname in favs_page:
        if fname.lower() == favorites_name.lower():
          # found it!
          logging.info('Picture folder %r = ID %d', fname, int(fid))
          self._db['favorites'].setdefault(user_id, {})[int(fid)] = {'name': fname, 'images': []}
          return (int(fid), fname)
      page_num += 1

  def AddFolderPics(self, user_id: int, folder_id: int) -> list[int]:
    """Read a folder and collect/compile all image IDs that are found, for all pages.

    Args:
      user_id: User int ID
      folder_id: Folder int ID

    Returns:
      list of all image ids
    """
    logging.info('Getting all picture folder pages and IDs for %d/%d', user_id, folder_id)
    img_list = self._db['favorites'].setdefault(user_id, {}).setdefault(
        folder_id, {'name': '???', 'images': []})['images']
    img_set = set(img_list)

    def _ExtractFavoriteIDs(page_num: int) -> list[int]:
      """Get numerical IDs of all images in a picture folder by URL.

      Args:
        page_num: Page to request (starting on 0!)

      Returns:
        list of integer image IDs; empty list on last (empty) page
      """
      url = _FOLDER_URL(user_id, folder_id, page_num)
      logging.info('Fetching favorites page: %s', url)
      fav_html = LimpingURLRead(url).decode('utf-8')
      ids = [int(id) for id in _FAV_IMG_RE.findall(fav_html)]
      logging.info('Got %d image IDs', len(ids))
      return ids

    # get the pages of links, until they end
    page_num = 0
    while True:
      new_ids = _ExtractFavoriteIDs(page_num)
      if not new_ids:
        break
      # add the images to the end, preserve order, but skip the ones already there
      for i in new_ids:
        if i not in img_set:
          img_list.append(i)
      img_set = set(img_list)
      page_num += 1
    logging.info('Found a total of %d image IDs in %d pages', len(img_list), page_num)
    return img_list

  def DownloadFavs(self, user_id: int, folder_id: int, output_path: str) -> int:
    """Actually get the images in a picture folder.

    Args:
      user_id: User ID
      folder_id: Folder ID
      output_path: Output path

    Returns:
      int size of all bytes downloaded
    """
    logging.info('Downloading all images in folder %d/%d', user_id, folder_id)
    img_list = self._db['favorites'].setdefault(user_id, {}).setdefault(
        folder_id, {'name': '???', 'images': []})['images']
    blobs, imageidsidx = self._db['blobs'], self._db['imageidsidx']

    def _ExtractFullImageURL(img_id: int) -> tuple[str, str]:
      """Get URL path of the full resolution image by image ID.

      Args:
        img_id: The image numerical ID

      Returns:
        (image URL path, image name path)

      Raises:
        Error: for invalid URLs or full-res URL not found
      """
      url = _IMG_URL(img_id)
      logging.info('Fetching image page: %s', url)
      img_html = LimpingURLRead(url).decode('utf-8')
      full_res_urls = _FULL_IMG_RE.findall(img_html)
      if not full_res_urls:
        raise Error('No full resolution image in %s' % url)
      img_name = _IMG_NAME_RE.findall(img_html)
      if not img_name:
        raise Error('No image name path in %s' % url)
      return (full_res_urls[0], img_name[0])

    def _SaveImage(url: str, name: str, dir_path: str) -> tuple[str, int, str]:
      """Get an image by URL and save to directory. Will sanitize the file name if needed.

      Args:
        url: Image URL path
        name: Image (unsanitized) name
        dir_path: Local disk directory path

      Returns:
        (the image sha256 hexdigest, the retrieved image bytes length, sanitized name)

      Raises:
        Error: for invalid URLs or empty images
      """
      logging.info('Fetching full-res image: %s', url)
      img = LimpingURLRead(url)
      if not img:
        raise Error('Empty full-res URL: %s' % url)
      sz = len(img)
      new_name = sanitize_filename.sanitize(name)
      if new_name != name:
        logging.warning('Filename sanitization necessary %r ==> %r', name, new_name)
      full_path = os.path.join(dir_path, new_name)
      with open(full_path, 'wb') as f:
        f.write(img)
      sha = hashlib.sha256(img).hexdigest()
      logging.info('Got %s for image %s (%s)', base.HumanizedLength(sz), full_path, sha)
      return (sha, sz, new_name)

    # dowload all full resolution images
    total_sz = 0
    for img_id in img_list:
      url_path, full_name = _ExtractFullImageURL(img_id)
      sha, sz, new_name = _SaveImage(url_path, full_name, output_path)
      blobs.setdefault(sha, {'loc': set(), 'tags': set()})['loc'].add(
          (img_id, url_path, new_name, user_id, folder_id))
      imageidsidx[img_id] = sha
      total_sz += sz
    # all images were downloaded, the end
    print('Saved %d images to disk (%s)' % (len(img_list), base.HumanizedLength(total_sz)))
    return total_sz
