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
from typing import Literal, Union
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
_DB_KEY_TYPE = Literal['users', 'favorites', 'tags', 'blobs', 'imageidsidx']

# the site page templates we need
_USER_PAGE_URL = lambda n: 'https://www.imagefap.com/profile/%s' % n
_FAVS_URL = lambda u, p: 'https://www.imagefap.com/showfavorites.php?userid=%d&page=%d' % (u, p)
_FOLDER_URL = lambda u, f, p: '%s&folderid=%d' % (_FAVS_URL(u, p), f)
_IMG_URL = lambda id: 'https://www.imagefap.com/photo/%d/' % id

# the regular expressions we use to navigate the pages
_FIND_NAME_IN_FAVS = re.compile(
    r'<a\s+class=.blk_header.\s+href="\/profile\.php\?user=(.*)"\s+style="')
_FIND_USER_ID_RE = re.compile(
    r'<a\s+class=.blk_header.\s+href="\/showfavorites.php\?userid=([0-9]+)".*>')
_FIND_ACTUAL_NAME = re.compile(r'<td\s+class=.blk_profile_hdr.*>(.*)\sProfile\s+<\/td>')
_FIND_NAME_IN_FOLDER = re.compile(
    r'<a\s+class=.blk_favorites.\s+href=".*none;">(.*)<\/a><\/td><\/tr>')
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

  def __init__(self, path):
    """Construct a clean database.

    Args:
      path: The file path to load/save DB from

    Raises:
      AttributeError: on empty path
    """
    # start with a clean DB; see README.md for format
    if not path:
      raise AttributeError('Database path cannot be empty')
    self._path: str = path
    self._db: dict[_DB_KEY_TYPE, dict] = {}
    for k in _DB_MAIN_KEYS:  # creates the main expected key entries
      self._db[k] = {}  # type: ignore

  @property
  def _users(self) -> dict[int, str]:
    return self._db['users']

  @property
  def _favorites(self) -> dict[int, dict[int, dict[Literal['name', 'images'],
                                                   Union[str, list[int]]]]]:
    return self._db['favorites']

  @property
  def _tags(self) -> dict[int, dict[Literal['name', 'tags'], Union[str, dict]]]:
    return self._db['tags']

  @property
  def _blobs(self) -> dict[str, dict[Literal['loc', 'tags'],
                                     set[Union[int, tuple[int, str, str, int, int]]]]]:
    return self._db['blobs']

  @property
  def _imageidsidx(self) -> dict[int, str]:
    return self._db['imageidsidx']

  def Load(self) -> None:
    """Load DB from file.

    Raises:
      Error: if found DB does not check out
    """
    if os.path.exists(self._path):
      self._db = base.BinDeSerialize(file_path=self._path)
      # just a quick dirty check that we got what we expected
      if any(k not in self._db for k in _DB_MAIN_KEYS):
        raise Error('Loaded DB is invalid!')
      logging.info('Loaded DB from %r', self._path)
    else:
      logging.warning('No DB found in %r', self._path)

  def Save(self) -> None:
    """Save DB to file."""
    base.BinSerialize(self._db, self._path)
    logging.info('Saved DB to %r', self._path)

  def AddUserByID(self, user_id: int) -> str:
    """Add user by ID and find user name in the process.

    Args:
      user_id: The user ID

    Returns:
      actual user name

    Raises:
      Error: if conversion failed
    """
    if user_id in self._users:
      status = 'Known'
    else:
      status = 'New'
      url = _FAVS_URL(user_id, 0)  # use the favs page
      logging.info('Fetching favorites page: %s', url)
      user_html = LimpingURLRead(url).decode('utf-8')
      user_names = _FIND_NAME_IN_FAVS.findall(user_html)
      if len(user_names) != 1:
        raise Error('Could not find user name for %d' % user_id)
      self._users[user_id] = user_names[0]
    logging.info('%s user ID %d = %r', status, user_id, self._users[user_id])
    return self._users[user_id]

  def AddUserByName(self, user_name: str) -> tuple[int, str]:
    """Add user by handle. Find user ID in the process.

    Args:
      user_name: The given user name

    Returns:
      (int user ID, actual user name)

    Raises:
      Error: if conversion failed
    """
    # first try to find in DB
    for uid, unm in self._users.items():
      if unm.lower() == user_name.lower():
        logging.info('Known user %r = ID %d', unm, uid)
        return (uid, unm)
    # not found: we have to find in actual site
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
    logging.info('New user %r = ID %d', actual_name[0], uid)
    self._users[uid] = actual_name[0]
    return (uid, actual_name[0])

  def AddFolderByID(self, user_id: int, folder_id: int) -> str:
    """Add folder by ID and find folder name in the process.

    Args:
      user_id: User int ID
      folder_id: Folder int ID

    Returns:
      actual folder name

    Raises:
      Error: if conversion failed
    """
    if folder_id in self._favorites.get(user_id, {}):
      status = 'Known'
    else:
      status = 'New'
      url = _FOLDER_URL(user_id, folder_id, 0)  # use the folder page
      logging.info('Fetching favorites page: %s', url)
      folder_html = LimpingURLRead(url).decode('utf-8')
      folder_names = _FIND_NAME_IN_FOLDER.findall(folder_html)
      if len(folder_names) != 1:
        raise Error('Could not find folder name for %d/%d' % (user_id, folder_id))
      self._favorites.setdefault(user_id, {})[folder_id] = {
          'name': folder_names[0], 'images': []}
    logging.info('%s folder ID %d/%d = %r',
                 status, user_id, folder_id, self._favorites[user_id][folder_id]['name'])
    return self._favorites[user_id][folder_id]['name']  # type: ignore

  def AddFolderByName(self, user_id: int, favorites_name: str) -> tuple[int, str]:
    """Add picture folder by name. Find folder ID in the process.

    Args:
      user_id: The user's int ID
      favorites_name: The given picture folder name

    Returns:
      (int picture folder ID, actual folder name)

    Raises:
      Error: if conversion failed
    """
    # first try to find in DB
    if user_id in self._favorites:
      for fid, fdata in self._favorites[user_id].items():
        if fdata['name'].lower() == favorites_name.lower():  # type: ignore
          logging.info('Known picture folder %r = ID %d', fdata['name'], fid)
          return (fid, fdata['name'])  # type: ignore
    # not found: we have to find in actual site
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
          self._favorites.setdefault(user_id, {})[int(fid)] = {'name': fname, 'images': []}
          logging.info('New picture folder %r = ID %d', fname, int(fid))
          return (int(fid), fname)
      page_num += 1

  def AddFolderPics(self, user_id: int, folder_id: int) -> list[int]:
    """Read a folder and collect/compile all image IDs that are found, for all pages.

    This always goes through all favorite pages, as we want to always
    find new images, and it counts how many are new.

    Args:
      user_id: User int ID
      folder_id: Folder int ID

    Returns:
      list of all image ids
    """
    logging.info('Getting all picture folder pages and IDs for %d/%d', user_id, folder_id)
    img_list: list[int] = self._favorites.setdefault(user_id, {}).setdefault(
        folder_id, {'name': '???', 'images': []})['images']  # type: ignore
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
    page_num, new_count = 0, 0
    while True:
      new_ids = _ExtractFavoriteIDs(page_num)
      if not new_ids:
        break
      # add the images to the end, preserve order, but skip the ones already there
      for i in new_ids:
        if i not in img_set:
          img_list.append(i)
          new_count += 1
      img_set = set(img_list)
      page_num += 1
    logging.info(
        'Found a total of %d image IDs in %d pages (%d are new in set, %d need downloading)',
        len(img_list), page_num, new_count, sum(1 for i in img_list if i not in self._imageidsidx))
    return img_list

  def DownloadFavs(self, user_id: int, folder_id: int,  # noqa: C901
                   output_path: str, checkpoint_size: int = 0) -> int:
    """Actually get the images in a picture folder.

    Args:
      user_id: User ID
      folder_id: Folder ID
      output_path: Output path
      checkpoint_size: (default 0) Commit database to disk every `checkpoint_size`
          images actually downloaded; if zero will not checkpoint at all

    Returns:
      int size of all bytes downloaded
    """
    logging.info('Downloading all images in folder %d/%d', user_id, folder_id)
    if checkpoint_size:
      logging.info('Will checkpoint DB every %d downloaded images', checkpoint_size)
    else:
      logging.warning('Will NOT checkpoint DB - work may be lost')
    img_list: list[int] = self._favorites.setdefault(user_id, {}).setdefault(
        folder_id, {'name': '???', 'images': []})['images']  # type: ignore

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

    # dowload all full resolution images we don't yet have
    total_sz, saved_count, known_count, dup_count = 0, 0, 0, 0
    for img_id in img_list:
      # figure out if we have it
      sha = self._imageidsidx.get(img_id, None)
      if sha is not None:
        found = False
        for i, _, n, uid, fid in self._blobs[sha]['loc']:  # type: ignore
          if user_id == uid and folder_id == fid:
            # this is an exact match and can be safely skipped
            found = True
            logging.info('Image %d/%r is already in DB from this album', i, n)
            break
        if found:
          known_count += 1
          continue
      # get the image's full resolution URL
      url_path, full_name = _ExtractFullImageURL(img_id)
      if sha is None:
        # we never saw this image, so we create a full entry
        sha, sz, new_name = _SaveImage(url_path, full_name, output_path)
        self._blobs.setdefault(sha, {'loc': set(), 'tags': set()})['loc'].add(
            (img_id, url_path, new_name, user_id, folder_id))
        self._imageidsidx[img_id] = sha
        total_sz += sz
        saved_count += 1
        if checkpoint_size and not saved_count % checkpoint_size:
          self.Save()
      else:
        # we have this image in a blob, so we only update the blob indexing
        logging.info('Image %d/%r does not need downloading', img_id, full_name)
        self._blobs[sha]['loc'].add((img_id, url_path, full_name, user_id, folder_id))
        dup_count += 1
    # all images were downloaded, the end
    print(
        'Saved %d images to disk (%s); also %d images were already in DB and '
        '%d images were duplicates from other albums' % (
            saved_count, base.HumanizedLength(total_sz), known_count, dup_count))
    return total_sz
