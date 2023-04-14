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

import base64
import enum
import getpass
import html
import logging
import math
import os
import os.path
# import pdb
import random
import shutil
import statistics
import tempfile
from typing import Iterator, Optional, TypedDict

from PIL import Image, ImageSequence
import numpy as np
import requests

from baselib import base
from fapfavorites import fapbase
from fapfavorites import duplicates


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


# useful globals
DEFAULT_DB_DIRECTORY = '~/Downloads/imagefap/'
_DEFAULT_DB_NAME = 'imagefap.database'
_DEFAULT_BLOB_DIR_NAME = 'blobs/'
DEFAULT_THUMBS_DIR_NAME = 'thumbs/'
_THUMBNAIL_MAX_DIMENSION = 280
CHECKPOINT_LENGTH = 10         # int number of downloads between database checkpoints
AUDIT_CHECKPOINT_LENGTH = 100  # int number of audits between database checkpoints
FAVORITES_MIN_DOWNLOAD_WAIT = 3 * (60 * 60 * 24)  # 3 days (in seconds)
AUDIT_MIN_DOWNLOAD_WAIT = 10 * (60 * 60 * 24)     # 10 days (in seconds)


# internal types definitions
class _FailureLevel(enum.Enum):
  """Audit image failure depths."""

  IMAGE_PAGE = 1
  URL_EXTRACTION = 2
  FULL_RES = 3


LocationKeyType = tuple[int, int, int]  # (user_id, folder_id, image_id)
LocationValueType = tuple[str, duplicates.IdenticalVerdictType]
_LocationType = dict[LocationKeyType, LocationValueType]
_GoneTupleType = tuple[int, _FailureLevel, str]
_GoneType = dict[int, _GoneTupleType]


class _ConfigsType(TypedDict):
  """Configurations type."""

  duplicates_sensitivity_regular: duplicates._SensitivitiesType
  duplicates_sensitivity_animated: duplicates._SensitivitiesType


class _UserObjType(TypedDict):
  """User object type."""

  name: str
  date_albums: int
  date_finished: int
  date_audit: int


class _FavoriteObjType(TypedDict):
  """Favorite object type."""

  name: str
  pages: int
  date_blobs: int
  images: list[int]
  failed_images: set[fapbase.FailedTupleType]


class TagObjType(TypedDict):
  """Tag object type."""

  name: str
  tags: dict[int, dict]


class _BlobObjType(TypedDict):
  """Blob object type."""

  loc: _LocationType
  tags: set[int]
  sz: int
  sz_thumb: int
  ext: str
  percept: str
  average: str
  diff: str
  wavelet: str
  cnn: np.ndarray
  width: int
  height: int
  animated: bool
  date: int
  gone: _GoneType


_UserType = dict[int, _UserObjType]
_FavoriteType = dict[int, dict[int, _FavoriteObjType]]
_TagType = dict[int, TagObjType]
_BlobType = dict[str, _BlobObjType]
_ImagesIdIndexType = dict[int, str]
_DB_MAIN_KEYS = {'configs', 'users', 'favorites', 'tags', 'blobs', 'image_ids_index',
                 'duplicates_registry', 'duplicates_key_index'}


class _DatabaseType(TypedDict):
  """Database type."""

  configs: _ConfigsType
  users: _UserType
  favorites: _FavoriteType
  tags: _TagType
  blobs: _BlobType
  image_ids_index: _ImagesIdIndexType
  duplicates_registry: duplicates.DuplicatesType
  duplicates_key_index: duplicates.DuplicatesKeyIndexType


class Error(fapbase.Error):
  """Base fap DB exception."""


class FapDatabase:
  """Imagefap.com database."""

  def __init__(self, dir_path: str, create_if_needed: bool = True):
    """Construct a clean database. Does *not* load or save or create/check files at this stage.

    Also initializes random number generator.

    Args:
      path: The directory path to load/save DB and images from/to
      create_if_needed: (default True) If True, Creates DB directory if not present;
          If False, will raise Error if not present

    Raises:
      AttributeError: on empty dir_path, or for create_if_needed==False, if dir_path not present
    """
    random.seed()
    if not dir_path:
      raise AttributeError('Output directory path cannot be empty')
    logging.info('Database directory will be: %r', dir_path)
    # start with a clean DB; see README.md for format
    self._original_dir = dir_path                                            # what the user gave us
    self._db_dir = os.path.expanduser(self._original_dir)                    # where to put DB
    self._db_path = os.path.join(self._db_dir, _DEFAULT_DB_NAME)             # actual DB path
    self._blobs_dir = os.path.join(self._db_dir, _DEFAULT_BLOB_DIR_NAME)     # where to put blobs
    self._thumbs_dir = os.path.join(self._db_dir, DEFAULT_THUMBS_DIR_NAME)   # thumbnails dir
    self._key: Optional[bytes] = None  # Fernet crypto key in use; None = crypto not in use
    self._sha_encoder: Optional[base.BlockEncoder256] = None  # encoder for SHA256 digests
    self._db: _DatabaseType = {  # creates empty DB
        'configs': {
            'duplicates_sensitivity_regular': duplicates.METHOD_SENSITIVITY_DEFAULTS.copy(),
            'duplicates_sensitivity_animated': duplicates.ANIMATED_SENSITIVITY_DEFAULTS.copy(),
        },
        'users': {},
        'favorites': {},
        'tags': {},
        'blobs': {},
        'image_ids_index': {},
        'duplicates_registry': {},
        'duplicates_key_index': {},
    }
    self.duplicates = duplicates.Duplicates(self._duplicates_registry, self._duplicates_key_index)
    # check output directory, create if needed
    if (not create_if_needed and
        (not os.path.isdir(self._db_dir) or
         not self.blobs_dir_exists or
         not self.thumbs_dir_exists)):
      raise Error(f'Output directories {self._original_dir!r}/ + /blobs & /thumb do not exist')
    if not os.path.isdir(self._db_dir):
      logging.info('Creating output directory %r', self._original_dir)
      os.mkdir(self._db_dir)
    # create blobs & thumbnails directories, if needed
    if not self.blobs_dir_exists:
      logging.info('Creating blob directory %r', self._blobs_dir)
      os.mkdir(self._blobs_dir)
    if not self.thumbs_dir_exists:
      logging.info('Creating thumbnails directory %r', self._thumbs_dir)
      os.mkdir(self._thumbs_dir)
    # save to environment: "changes will be effective only for the current process where it was
    # assigned and it will not change the value permanently", so the variable won't leak to the
    # larger system; Also: "This mapping is captured the first time the os module is imported,
    # typically during Python startup [...] Changes to the environment made after this time are
    # not reflected in os.environ, except for changes made by modifying os.environ directly."
    os.environ['IMAGEFAP_FAVORITES_DB_PATH'] = self._original_dir
    if os.environ.get('IMAGEFAP_FAVORITES_DB_KEY', None) is not None:
      logging.warning('DB loading pre-existing environment key')
      self._key = os.environ['IMAGEFAP_FAVORITES_DB_KEY'].encode('utf-8')
      self._sha_encoder = base.BlockEncoder256(base64.urlsafe_b64decode(self._key))

  @property
  def configs(self) -> _ConfigsType:
    """Configurations dictionary."""
    return self._db['configs']

  @property
  def users(self) -> _UserType:
    """Users dictionary."""
    return self._db['users']

  @property
  def favorites(self) -> _FavoriteType:
    """Favorites dictionary."""
    return self._db['favorites']

  @property
  def tags(self) -> _TagType:
    """Tags dictionary."""
    return self._db['tags']

  @property
  def blobs(self) -> _BlobType:
    """Blobs dictionary."""
    return self._db['blobs']

  @property
  def image_ids_index(self) -> _ImagesIdIndexType:
    """Images IDs index dictionary."""
    return self._db['image_ids_index']

  @property
  def _duplicates_registry(self) -> duplicates.DuplicatesType:
    """Duplicates dictionary."""
    return self._db['duplicates_registry']

  @property
  def _duplicates_key_index(self) -> duplicates.DuplicatesKeyIndexType:
    """Duplicates key index."""
    return self._db['duplicates_key_index']

  @property
  def blobs_dir_exists(self) -> bool:
    """True if blobs directory path is in existence."""
    return os.path.isdir(self._blobs_dir)

  @property
  def thumbs_dir_exists(self) -> bool:
    """True if thumbnails directory path is in existence."""
    return os.path.isdir(self._thumbs_dir)

  def Load(self) -> bool:
    """Load DB from file. If no DB file does not do anything.

    Returns:
      True if a file was found and loaded, False if not

    Raises:
      Error: if found DB does not check out
    """
    if os.path.exists(self._db_path):
      with base.Timer() as tm_load:
        # we turned compression off: it was responsible for ~95% of save time
        try:
          # try to load the DB with what we have first, no user intervention
          self._db: _DatabaseType = base.BinDeSerialize(
              file_path=self._db_path, compress=False, key=self._key)
        except base.pickle.UnpicklingError:
          # could not load it: if we don't have a key, we might ask for one
          if self._key is not None:
            raise
          logging.info('Vanilla DB could not be loaded, will try a crypto DB')
          self._key = base.DeriveKeyFromStaticPassword(
              getpass.getpass(prompt='Database Password: '))
          self._db: _DatabaseType = base.BinDeSerialize(
              file_path=self._db_path, compress=False, key=self._key)
          # the key seems to have worked, so we save it to environment: "changes will be effective
          # only for the current process where it was assigned and it will not change the value
          # permanently", so the variable won't leak to the larger operating system; Also:
          # "This mapping is captured the first time the os module is imported, typically
          # during Python startup [...] Changes to the environment made after this time are
          # not reflected in os.environ, except for changes made by modifying os.environ directly."
          os.environ['IMAGEFAP_FAVORITES_DB_KEY'] = self._key.decode('utf-8')
          self._sha_encoder = base.BlockEncoder256(base64.urlsafe_b64decode(self._key))
        # just a quick dirty check that we got what we expected
        if any(k not in self._db for k in _DB_MAIN_KEYS):
          raise Error('Loaded DB is invalid!')
        self.duplicates = duplicates.Duplicates(  # has to be reloaded!
            self._duplicates_registry, self._duplicates_key_index)
      logging.info(
          'Loaded %s DB from %r (%s)',
          'a VANILLA (unencrypted)' if self._key is None else 'an ENCRYPTED',
          self._db_path, tm_load.readable)
      return True
    # creating a new DB
    logging.warning('No DB found in %r: we are creating a new one', self._db_path)
    user_password1 = getpass.getpass(
        prompt='NEW Database Password (`Enter` key for no encryption): ')
    user_password2 = getpass.getpass(
        prompt='CONFIRM Database Password (`Enter` key for no encryption): ')
    if user_password1 != user_password2:
      raise Error('Password mismatch: please type the same password twice!')
    if not user_password1 or not user_password1.strip():
      self._key = None
      self._sha_encoder = None
      logging.warning('Database will be created WITHOUT a password, and any user can open it')
    else:
      self._key = base.DeriveKeyFromStaticPassword(user_password1)
      self._sha_encoder = base.BlockEncoder256(base64.urlsafe_b64decode(self._key))
      os.environ['IMAGEFAP_FAVORITES_DB_KEY'] = self._key.decode('utf-8')  # see comment above!
      logging.warning('Database will be created with a password')
    return False

  def Save(self) -> None:
    """Save DB to file."""
    with base.Timer() as tm_save:
      # we turned compression off: it was responsible for ~95% of save time
      base.BinSerialize(self._db, file_path=self._db_path, compress=False, key=self._key)
    logging.info(
        'Saved %s DB to %r (%s)',
        'a VANILLA (unencrypted)' if self._key is None else 'an ENCRYPTED',
        self._db_path, tm_save.readable)

  def UserStr(self, user_id: int) -> str:
    """Produce standard user representation, like 'UserName (id)'."""
    try:
      return f'{self.users[user_id]["name"]} ({user_id})'
    except KeyError as err:
      raise Error(f'User {user_id} not found') from err

  def AlbumStr(self, user_id: int, folder_id: int) -> str:
    """Produce standard album representation, like 'UserName/FolderName (uid/fid)'."""
    try:
      return (f'{self.users[user_id]["name"]}/{self.favorites[user_id][folder_id]["name"]} '
              f'({user_id}/{folder_id})')
    except KeyError as err:
      raise Error(f'Album {user_id}/{folder_id} not found') from err

  def LocationStr(self, key: LocationKeyType, value: LocationValueType) -> str:
    """Produce standard location repr, like 'UserName/FolderName/ImageName (uid/fid/img_id)'."""
    try:
      return (f'{self.users[key[0]]["name"]}/{self.favorites[key[0]][key[1]]["name"]}/{value[0]!r} '
              f'({key[0]}/{key[1]}/{key[2]})')
    except KeyError as err:
      raise Error(f'Invalid location {key!r}/{value!r}') from err

  def LocationsStr(self, location: _LocationType) -> str:
    """Produce standard locations repr, like 'loc1 + loc2 + ...' where each one is a LocationStr."""
    return ' + '.join(self.LocationStr(loc_k, location[loc_k]) for loc_k in sorted(location.keys()))

  def TagStr(self, tag_id: int, add_id: bool = True) -> str:
    """Produce standard tag representation, like 'TagName (id)'."""
    name = self.GetTag(tag_id)[-1][1]
    return f'{name} ({tag_id})' if add_id else name

  def TagLineageStr(self, tag_id: int, add_id: bool = True) -> str:
    """Print tag name together with parents, like 'grand_name/parent_name/tag_name (id)'."""
    name = '/'.join(n for _, n, _ in self.GetTag(tag_id))
    return f'{name} ({tag_id})' if add_id else name

  def _BlobPath(self, sha: str, extension_hint: Optional[str] = None) -> str:
    """Get full disk file path for a blob hash (`sha`).

    Args:
      sha: the SHA-256
      extension_hint: (Default None) optional file extension to use; if *not* given the SHA must
          be available in the blobs database so extension can be known; if given will return a
          valid path even if SHA is still not listed in the database

    Returns:
      full file path of the blob file on disk (encrypted or not)

    Raises:
      Error: if SHA does not exist in self.blobs and `extension_hint` was not provided
    """
    try:
      disk_sha = sha if self._sha_encoder is None else self._sha_encoder.EncryptHexdigest256(sha)
      return os.path.join(
          self._blobs_dir,
          f'{disk_sha}.{self.blobs[sha]["ext"] if extension_hint is None else extension_hint}')
    except KeyError as err:
      raise Error(f'Blob {sha!r} not found') from err

  def _ThumbnailPath(self, sha: str, extension_hint: Optional[str] = None) -> str:
    """Get full disk file path for a thumbnail, based on its blob's hash (`sha`).

    Args:
      sha: the SHA-256
      extension_hint: (Default None) optional file extension to use; if *not* given the SHA must
          be available in the blobs database so extension can be known; if given will return a
          valid path even if SHA is still not listed in the database

    Returns:
      full file path of the thumbnail file on disk (encrypted or not)

    Raises:
      Error: if SHA does not exist in self.blobs and `extension_hint` was not provided
    """
    try:
      disk_sha = sha if self._sha_encoder is None else self._sha_encoder.EncryptHexdigest256(sha)
      return os.path.join(
          self._thumbs_dir,
          f'{disk_sha}.{self.blobs[sha]["ext"] if extension_hint is None else extension_hint}')
    except KeyError as err:
      raise Error(f'Thumbnail {sha!r} not found') from err

  def HasBlob(self, sha: str) -> bool:
    """Check if blob `sha` is available in blobs/ directory."""
    return os.path.exists(self._BlobPath(sha))

  def HasThumbnail(self, sha: str) -> bool:
    """Check if thumbnail `sha` is available in thumbs/ directory."""
    return os.path.exists(self._ThumbnailPath(sha))

  def GetBlob(self, sha: str) -> bytes:
    """Get the blob binary data for `sha` entry (decrypts it if needed)."""
    with open(self._BlobPath(sha), 'rb') as file_obj:
      raw_data = file_obj.read()
    return raw_data if self._key is None else base.Decrypt(raw_data, self._key)

  def GetThumbnail(self, sha: str) -> bytes:
    """Get the thumbnail binary data for `sha` entry (decrypts it if needed)."""
    with open(self._ThumbnailPath(sha), 'rb') as file_obj:
      raw_data = file_obj.read()
    return raw_data if self._key is None else base.Decrypt(raw_data, self._key)

  def _SHAFromFileName(self, file_name: str) -> str:
    """Get database blob/thumb hash (SHA-256) from file name on disk.

    Args:
      file_name: the file name (without directory, just file name)

    Returns:
      SHA to use in DB from the file name

    Raises:
      Error: if file format is unexpected and can't be processed
    """
    try:
      digest, _ = file_name.strip().lower().split('.', maxsplit=1)  # cspell:disable-line
      if len(digest) != 64:
        raise ValueError('Expected 64 chars in file name (256 bits of hexadecimal)')
      return digest if self._sha_encoder is None else self._sha_encoder.DecryptHexdigest256(digest)
    except ValueError as err:
      raise Error('Unexpected or invalid blob/thumb file name {file_name!r}') from err

  def GetTag(self, tag_id: int) -> list[tuple[int, str, TagObjType]]:  # noqa: C901
    """Search recursively for specific tag object, returning parents too, if any.

    Args:
      tag_id: The wanted tag ID

    Returns:
      list of (id, name, tag_obj), starting with the parents and ending with the wanted tag;
      this means that GetTag(id)[-1] is always the wanted tag tuple

    Raises:
      Error: not found or invalid
    """
    if not tag_id:
      raise Error('tag_id cannot be empty')
    hierarchy: list[tuple[int, str, TagObjType]] = []

    def _GetRecursive(obj: _TagType) -> bool:
      if tag_id in obj:
        try:
          hierarchy.append((tag_id, obj[tag_id]['name'], obj[tag_id]))  # found!
        except KeyError as err:
          raise Error(f'Found tag {tag_id} is empty (has no \'name\')!') from err
        return True
      for i, inner_obj in obj.items():
        if inner_obj.get('tags', {}):
          if _GetRecursive(inner_obj['tags']):  # type: ignore
            try:
              hierarchy.append((i, inner_obj['name'], inner_obj))  # parent to a found tag
            except KeyError as err:
              raise Error(f'Parent tag {i} (of {tag_id}) is empty (has no \'name\')!') from err
            return True
      return False

    if not _GetRecursive(self.tags):
      raise Error(f'Tag ID {tag_id} was not found')
    hierarchy.reverse()
    return hierarchy

  def TagsWalk(
      self, start_tag: Optional[_TagType] = None, depth: int = 0) -> Iterator[
          tuple[int, str, int, _TagType]]:
    """Walk all tags recursively, depth first.

    Args:
      start_tag: (Default None) The tag to start at; None means start at root
      depth: (Default 0) DO NOT USE - Internal depth count

    Yields:
      (tag_id, tag_name, depth, sub_tags)
    """
    if start_tag is None:
      start_tag = self.tags
    for tag_name, tag_id, tag_tags in sorted(
        (t['name'], k, t['tags']) for k, t in start_tag.items()):  # will sort by name in this level
      yield (tag_id, tag_name, depth, tag_tags)  # type: ignore
      if start_tag[tag_id]['tags']:
        for obj in self.TagsWalk(
            start_tag=start_tag[tag_id]['tags'], depth=depth + 1):  # type: ignore
          yield obj

  def _TagNameOKOrDie(self, new_tag_name: str) -> None:
    """Check tag name is OK: does not clash and has no invalid chars. If not will raise exception.

    Args:
      new_tag_name: The proposed tag name to use

    Raises:
      Error: if tag name clashes with existing tags or if tag name has forbidden chars
    """
    # check for invalid chars
    if '/' in new_tag_name or '\\' in new_tag_name:
      raise Error(f'Don\'t use "/" or "\\" in tag name (tried to use {new_tag_name!r} as tag name)')
    # check if name does not clash with any already existing tag
    for tid, name, _, _ in self.TagsWalk():
      if new_tag_name.lower() == name.lower():
        raise Error(
            f'Proposed tag name {new_tag_name!r} clashes with existing tag {self.TagStr(tid)}')

  def AddTag(self, parent_id: int, new_tag_name: str) -> int:
    """Add new tag.

    Args:
      parent_id: The parent to add the tag under; zero (0) means root
      new_tag_name: The proposed tag name to use

    Returns:
      the new tag ID

    Raises:
      Error: on failure
    """
    # check tag name and find the parent
    self._TagNameOKOrDie(new_tag_name)
    parent_obj = self.GetTag(parent_id)[-1][-1]['tags'] if parent_id else self.tags
    # tag name is OK: find a free ID by incrementing until we hit one (inefficient but will do...)
    all_tag_ids = {tid for tid, _, _, _ in self.TagsWalk()}
    current_id = 1
    while current_id in all_tag_ids:
      current_id += 1
    # we have a number, so insert the tag
    parent_obj[current_id] = {'name': new_tag_name, 'tags': {}}  # type: ignore
    return current_id

  def RenameTag(self, tag_id: int, new_tag_name: str) -> None:
    """Rename a tag.

    Args:
      tag_id: The tag ID to rename
      new_tag_name: The proposed tag name to use

    Raises:
      Error: on failure
    """
    # check tag name and find the object
    self._TagNameOKOrDie(new_tag_name)
    obj = self.GetTag(tag_id)[-1][-1]  # will raise if tag_id==0 (which is correct behavior)
    # tag name is OK: do the change
    obj['name'] = new_tag_name

  def DeleteTag(self, tag_id: int) -> set[str]:
    """Delete tag and remove all usage of the tag from the blobs.

    Args:
      tag_id: Tag ID to delete

    Returns:
      set of all SHA256 (blob keys) that had the tag removed

    Raises:
      Error: on failure
    """
    tag_hierarchy = self.GetTag(tag_id)
    # check tag does not have children
    if tag_hierarchy[-1][-1]['tags']:
      raise Error(
          f'Requested deletion of tag {self.TagLineageStr(tag_id)} that is not empty '
          '(delete children first)')
    # everything OK: do deletion
    if len(tag_hierarchy) < 2:
      # in this case it is a child of root
      del self.tags[tag_id]
    else:
      # in this case we have a non-root parent
      del tag_hierarchy[-2][-1]['tags'][tag_id]
    # we must remove the tags from any images that have it too!
    tag_deletions: set[str] = set()
    for sha, blob in self.blobs.items():
      if tag_id in blob['tags']:
        blob['tags'].remove(tag_id)
        tag_deletions.add(sha)
    return tag_deletions

  def PrintStats(self, actually_print=True) -> list[str]:
    """Print database stats.

    Args:
      actually_print: (default True) If true will print() the lines; else won't

    Returns:
      list of strings to print as status
    """
    file_sizes: list[int] = [s['sz'] for s in self.blobs.values()]
    thumb_sizes: list[int] = [s['sz_thumb'] for s in self.blobs.values()]
    all_files_size, all_thumb_size = sum(file_sizes), sum(thumb_sizes)
    db_size = os.path.getsize(self._db_path)
    all_lines: list[str] = []

    def _PrintLine(line: str = ''):
      all_lines.append(line)
      if actually_print:
        print(line)

    _PrintLine(
        f'Database is located in {self._db_path!r}, and is {base.HumanizedBytes(db_size)} '
        f'({(100.0 * db_size) / (all_files_size if all_files_size else 1):0.3f}% of '
        'total images size)')
    _PrintLine(
        f'{base.HumanizedBytes(all_files_size)} total (unique) images size '
        f'({base.HumanizedBytes(min(file_sizes)) if file_sizes else "-"} min, '
        f'{base.HumanizedBytes(max(file_sizes)) if file_sizes else "-"} max, '
        f'{base.HumanizedBytes(int(statistics.mean(file_sizes))) if file_sizes else "-"} mean with '
        f'{base.HumanizedBytes(int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else "-"} '
        f'standard deviation, {sum(int(s["animated"]) for s in self.blobs.values())} are animated)')
    if file_sizes:
      wh_sizes: list[tuple[int, int]] = [
          (s['width'], s['height']) for s in self.blobs.values()]
      pixel_sizes: list[int] = [
          s['width'] * s['height'] for s in self.blobs.values()]
      std_dev = base.HumanizedDecimal(
          int(statistics.stdev(pixel_sizes))) if len(pixel_sizes) > 2 else '-'
      _PrintLine(  # cspell:disable-line
          f'Pixel size (width, height): {base.HumanizedDecimal(min(pixel_sizes))} pixels min '
          f'{wh_sizes[pixel_sizes.index(min(pixel_sizes))]!r}, '
          f'{base.HumanizedDecimal(max(pixel_sizes))} pixels max '
          f'{wh_sizes[pixel_sizes.index(max(pixel_sizes))]!r}, '
          f'{base.HumanizedDecimal(int(statistics.mean(pixel_sizes)))} mean with '
          f'{std_dev} standard deviation')
    if all_files_size and all_thumb_size:
      std_dev = base.HumanizedBytes(
          int(statistics.stdev(thumb_sizes))) if len(thumb_sizes) > 2 else '-'
      _PrintLine(
          f'{base.HumanizedBytes(all_thumb_size)} total thumbnail size ('
          f'{base.HumanizedBytes(min(thumb_sizes)) if thumb_sizes else "-"} min, '
          f'{base.HumanizedBytes(max(thumb_sizes)) if thumb_sizes else "-"} max, '
          f'{base.HumanizedBytes(int(statistics.mean(thumb_sizes))) if thumb_sizes else "-"} mean '
          f'with {std_dev} standard deviation), '
          f'{(100.0 * all_thumb_size) / all_files_size:0.1f}% of total images size')
    _PrintLine()
    _PrintLine(f'{len(self.users)} users')
    all_dates = [fav['date_blobs'] for user in self.favorites.values() for fav in user.values()]
    min_date = min(all_dates) if all_dates else 0
    max_date = max(all_dates) if all_dates else 0
    _PrintLine(f'{sum(len(f) for _, f in self.favorites.items())} favorite galleries '
               f'(oldest: {base.STD_TIME_STRING(min_date) if min_date else "pending"} / '
               f'newer: {base.STD_TIME_STRING(max_date) if max_date else "pending"})')
    _PrintLine(
        f'{len(self.blobs)} unique images ({sum(len(b["loc"]) for b in self.blobs.values())} '
        f'total, {sum(len(b["loc"]) for b in self.blobs.values() if len(b["loc"]) > 1)} '
        'exact duplicates)')
    unique_failed: set[int] = set()
    for failed in (
        fav['failed_images'] for user in self.favorites.values() for fav in user.values()):
      unique_failed.update(img for img, _, _, _ in failed)
    _PrintLine(f'{len(unique_failed)} unique failed images in all user albums')
    _PrintLine(f'{sum(1 for b in self.blobs.values() if b["gone"])} unique images are now '
               'disappeared from imagefap site')
    _PrintLine(f'{len(self.duplicates.index)} perceptual duplicates in '
               f'{len(self.duplicates.registry)} groups')
    return all_lines

  def PrintUsersAndFavorites(self, actually_print=True) -> list[str]:
    """Print database users.

    Args:
      actually_print: (default True) If true will print() the lines; else won't

    Returns:
      list of strings to print as status
    """
    all_lines: list[str] = []

    def _PrintLine(line: str = ''):
      all_lines.append(line)
      if actually_print:
        print(line)

    _PrintLine('ID: USER_NAME')
    _PrintLine('    FILE STATS FOR USER')
    _PrintLine('    => ID: FAVORITE_NAME (IMAGE_COUNT / FAILED_COUNT / PAGE_COUNT / DATE DOWNLOAD)')
    _PrintLine('           FILE STATS FOR FAVORITES')
    for uid in sorted(self.users.keys()):
      _PrintLine()
      _PrintLine(f'{uid}: {self.users[uid]["name"]!r}')
      file_sizes: list[int] = [
          self.blobs[self.image_ids_index[i]]['sz']
          for d, u in self.favorites.items() if d == uid
          for f in u.values()
          for i in f['images'] if i in self.image_ids_index]
      std_dev = base.HumanizedBytes(
          int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else '-'
      _PrintLine(f'    {base.HumanizedBytes(sum(file_sizes) if file_sizes else 0)} files size '
                 f'({base.HumanizedBytes(min(file_sizes)) if file_sizes else "-"} min, '
                 f'{base.HumanizedBytes(max(file_sizes)) if file_sizes else "-"} max, '
                 f'{base.HumanizedBytes(int(statistics.mean(file_sizes))) if file_sizes else "-"} '
                 f'mean with {std_dev} standard deviation)')
      for fid in sorted(self.favorites.get(uid, {}).keys()):
        obj = self.favorites[uid][fid]
        file_sizes: list[int] = [
            self.blobs[self.image_ids_index[i]]['sz']
            for i in obj['images'] if i in self.image_ids_index]
        date_str = base.STD_TIME_STRING(obj['date_blobs']) if obj['date_blobs'] else 'pending'
        _PrintLine(f'    => {fid}: {obj["name"]!r} ({len(obj["images"])} / '
                   f'{len(obj["failed_images"])} / {obj["pages"]} / {date_str})')
        if file_sizes:
          std_dev = base.HumanizedBytes(
              int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else '-'
          _PrintLine(
              f'           {base.HumanizedBytes(sum(file_sizes))} files size '
              f'({base.HumanizedBytes(min(file_sizes))} min, '
              f'{base.HumanizedBytes(max(file_sizes))} max, '
              f'{base.HumanizedBytes(int(statistics.mean(file_sizes)))} mean with '
              f'{std_dev} standard deviation)')
    return all_lines

  def PrintTags(self, actually_print=True) -> list[str]:
    """Print database tags.

    Args:
      actually_print: (default True) If true will print() the lines; else won't

    Returns:
      list of strings to print as status
    """
    all_lines: list[str] = []

    def _PrintLine(line: str = ''):
      all_lines.append(line)
      if actually_print:
        print(line)

    if not self.tags:
      _PrintLine('NO TAGS CREATED')
      return all_lines
    _PrintLine('TAG_ID: TAG_NAME (NUMBER_OF_IMAGES_WITH_TAG / SIZE_OF_IMAGES_WITH_TAG)')
    _PrintLine()
    for tag_id, tag_name, depth, _ in self.TagsWalk():
      count: int = 0
      total_sz: int = 0
      for blob in self.blobs.values():
        if tag_id in blob['tags']:
          count += 1
          total_sz += blob['sz']
      _PrintLine(
          f'{"    " * depth}{tag_id}: {tag_name!r} ({count} / {base.HumanizedBytes(total_sz)})')
    return all_lines

  def PrintBlobs(self, actually_print=True) -> list[str]:
    """Print database blobs metadata.

    Args:
      actually_print: (default True) If true will print() the lines; else won't

    Returns:
      list of strings to print as status
    """
    all_lines: list[str] = []

    def _PrintLine(line: str = ''):
      all_lines.append(line)
      if actually_print:
        print(line)

    _PrintLine('SHA256_HASH: ID1/\'NAME1\' or ID2/\'NAME2\' or ..., PIXELS '
               '(WIDTH, HEIGHT) [ANIMATED]')
    _PrintLine('    => {\'TAG1\', \'TAG2\', ...}')
    _PrintLine()
    for sha in sorted(self.blobs.keys()):
      blob = self.blobs[sha]
      _PrintLine(f'{sha}: {self.LocationsStr(blob["loc"])}, '
                 f'{base.HumanizedDecimal(blob["width"] * blob["height"])} '
                 f'({blob["width"]}, {blob["height"]}){" animated" if blob["animated"] else ""}')
      if blob['tags']:
        _PrintLine(f'    => {{{", ".join(self.TagStr(tid) for tid in sorted(blob["tags"]))}}}')
    return all_lines

  def AddUserByID(self, user_id: int) -> str:
    """Add user by ID and find user name in the process.

    Args:
      user_id: The user ID

    Returns:
      actual user name

    Raises:
      Error: if conversion failed
    """
    if user_id in self.users:
      status = 'Known'
    else:
      status = 'New'
      actual_name = fapbase.GetUserDisplayName(user_id)  # will also serve as user_id check
      self.users[user_id] = {
          'name': actual_name, 'date_albums': 0, 'date_finished': 0, 'date_audit': 0}
    logging.info('%s user %s added', status, self.UserStr(user_id))
    return self.users[user_id]['name']

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
    for uid, user in self.users.items():
      if user['name'].lower() == user_name.lower():
        logging.info('Known user %s', self.UserStr(uid))
        return (uid, user['name'])
    # not found: we have to find in actual site
    uid = fapbase.ConvertUserName(user_name)
    return (uid, self.AddUserByID(uid))

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
    if folder_id in self.favorites.get(user_id, {}):
      status = 'Known'
    else:
      status = 'New'
      url: str = fapbase.FOLDER_URL(user_id, folder_id, 0)  # use the folder page
      logging.info('Fetching favorites page: %s', url)
      folder_html = fapbase.FapHTMLRead(url)
      folder_names: list[str] = fapbase.FIND_NAME_IN_FOLDER.findall(folder_html)
      if len(folder_names) != 1:
        raise Error(f'Could not find folder name for {user_id}/{folder_id}')
      fapbase.CheckFolderIsForImages(user_id, folder_id)  # raises Error if not valid
      self.favorites.setdefault(user_id, {})[folder_id] = {
          'name': html.unescape(folder_names[0]), 'pages': 0,
          'date_blobs': 0, 'images': [], 'failed_images': set()}
    logging.info('%s folder %s added', status, self.AlbumStr(user_id, folder_id))
    return self.favorites[user_id][folder_id]['name']

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
    if user_id in self.favorites:
      for fid, f_data in self.favorites[user_id].items():
        if f_data['name'].lower() == favorites_name.lower():
          logging.info('Known folder %s', self.AlbumStr(user_id, fid))
          return (fid, f_data['name'])
    # not found: we have to find in actual site
    folder_id, folder_name = fapbase.ConvertFavoritesName(user_id, favorites_name)
    self.favorites.setdefault(user_id, {})[folder_id] = {
        'name': folder_name, 'pages': 0, 'date_blobs': 0, 'images': [], 'failed_images': set()}
    logging.info('New folder %s added', self.AlbumStr(user_id, folder_id))
    return (folder_id, folder_name)

  def AddAllUserFolders(self, user_id: int, force_download: bool) -> set[int]:
    """Add all user's folders that are images galleries.

    Args:
      user_id: The user's int ID
      force_download: If True will download even if recently downloaded

    Returns:
      set of int folder IDs
    """
    try:
      # check for the timestamps: should we even do this work?
      if not self._CheckWorkHysteresis(
          force_download, self.users[user_id]['date_albums'],
          f'Getting all image favorites for user {self.UserStr(user_id)}'):
        return set(self.favorites.get(user_id, {}).keys())
    except KeyError as err:
      raise Error(f'This user was not added to DB yet: {user_id}') from err
    # get all pages of albums, extract the albums
    page_num: int = 0
    known_favorites: int = 0
    non_galleries: int = 0
    found_folder_ids: set[int] = set()
    self.favorites.setdefault(user_id, {})  # just to make sure user is in _favorites
    while True:
      url: str = fapbase.FAVORITES_URL(user_id, page_num)
      logging.info('Fetching favorites page: %s', url)
      fav_html = fapbase.FapHTMLRead(url)
      favorites_page: list[tuple[str, str]] = fapbase.FIND_FOLDERS.findall(fav_html)
      if not favorites_page:
        break  # no favorites found, so we passed the last page
      for f_id, f_name in favorites_page:
        i_f_id, f_name = int(f_id), html.unescape(f_name)
        # first check if we know it (for speed)
        if i_f_id in self.favorites[user_id]:
          # we already know of this gallery
          logging.info('Known picture folder %s', self.AlbumStr(user_id, i_f_id))
          found_folder_ids.add(i_f_id)
          known_favorites += 1
          continue
        # check if we can accept it as a images gallery
        try:
          fapbase.CheckFolderIsForImages(user_id, i_f_id)  # raises Error if not valid
        except fapbase.Error:
          # this is a galleries favorite, so we can skip: we want images gallery!
          logging.info('Discarded galleries folder %r (%d/%d)', f_name, user_id, i_f_id)
          non_galleries += 1
          continue
        # we seem to have a valid new favorite here
        found_folder_ids.add(i_f_id)
        self.favorites[user_id][i_f_id] = {
            'name': f_name, 'pages': 0, 'date_blobs': 0, 'images': [], 'failed_images': set()}
        logging.info('New picture folder %s added', self.AlbumStr(user_id, i_f_id))
      page_num += 1
    # mark the albums checking as done, log & return
    self.users[user_id]['date_albums'] = base.INT_TIME()
    logging.info('Found %d total favorite galleries in %d pages (%d were already known; '
                 'also, %d non-image galleries were skipped)',
                 len(found_folder_ids), page_num, known_favorites, non_galleries)
    return found_folder_ids

  def AddFolderPics(
      self, user_id: int, folder_id: int, force_download: bool) -> list[int]:
    """Read a folder and collect/compile all image IDs that are found, for all pages.

    This always goes through all favorite pages, as we want to always
    find new images, and it counts how many are new.

    Args:
      user_id: User int ID
      folder_id: Folder int ID
      force_download: If True will download even if recently downloaded

    Returns:
      list of all image ids
    """
    try:
      # check for the timestamps: should we even do this work?
      if not self._CheckWorkHysteresis(
          force_download, self.favorites[user_id][folder_id]['date_blobs'],
          f'Reading album {self.AlbumStr(user_id, folder_id)} pages & IDs'):
        return self.favorites[user_id][folder_id]['images']
      seen_img_list: list[int] = self.favorites[user_id][folder_id]['images']
      seen_pages: int = self.favorites[user_id][folder_id]['pages']
    except KeyError as err:
      raise Error(f'This user/folder was not added to DB yet: {user_id}/{folder_id}') from err
    # get the list and save the results
    img_list, page_num, new_count = fapbase.GetFolderPics(
        user_id, folder_id, img_list_hint=seen_img_list, seen_pages_hint=seen_pages)
    self.favorites[user_id][folder_id]['images'] = img_list
    self.favorites[user_id][folder_id]['pages'] = page_num
    logging.info(
        'Found a total of %d image IDs in %d pages (%d are new in set, %d need downloading)',
        len(img_list), page_num + 1, new_count,
        sum(1 for i in img_list if i not in self.image_ids_index))
    return img_list

  def _CheckWorkHysteresis(self, force_download: bool, tm_last: int, task_message: str) -> bool:
    """Check if work should be done, or if task has recently been finished.

    Args:
      force_download: If True will download even if recently downloaded
      tm_last: Time last download was done
      task_message: Type of work message to log

    Returns:
      True if work should be done; False otherwise
    """
    tm_now = base.INT_TIME()
    if tm_last and (tm_last + FAVORITES_MIN_DOWNLOAD_WAIT) > tm_now:
      logging.warning(
          '%s recently done (%s, %s ago): %s!',
          task_message, base.STD_TIME_STRING(tm_last), base.HumanizedSeconds(tm_now - tm_last),
          'ignoring time limit and downloading again' if force_download else 'SKIP')
      if not force_download:
        return False
    logging.info(task_message)
    return True

  def DownloadAll(  # noqa: C901
      self, user_id: int, folder_id: int, checkpoint_size: int, force_download: bool) -> int:
    """Actually get the images in a picture folder.

    Args:
      user_id: User ID
      folder_id: Folder ID
      checkpoint_size: Commit database to disk every `checkpoint_size` images actually downloaded;
          if zero will not checkpoint at all
      force_download: If True will download even if recently downloaded

    Returns:
      int size of all bytes downloaded

    Raises:
      Error: on inconsistencies
    """
    # check if work needs to be done
    try:
      if not self._CheckWorkHysteresis(
          force_download, self.favorites[user_id][folder_id]['date_blobs'],
          f'Downloading album {self.AlbumStr(user_id, folder_id)} images'):
        return 0
      logging.info('*NO* checkpoints used (work may be lost!)' if checkpoint_size == 0 else
                   f'Checkpoint DB every {checkpoint_size} downloads')
    except KeyError as err:
      raise Error(f'This user/folder was not added to DB yet: {user_id}/{folder_id}') from err
    # download all full resolution images we don't yet have
    total_sz: int = 0
    thumb_sz: int = 0
    total_thumb_sz: int = 0
    saved_count: int = 0
    known_count: int = 0
    exists_count: int = 0
    failed_count: int = 0
    for img_id in list(self.favorites[user_id][folder_id]['images']):  # copy b/c we might change it
      # figure out if we have it in the index, i.e., if we've seen img_id before
      sha = self.image_ids_index.get(img_id, None)
      sanitized_image_name: str = 'unknown'
      if sha is not None and self.HasBlob(sha):
        # we have seen this img_id before, and can skip a lot of stuff
        # also: we only have to add it if it is not an exact match user_id+folder_id+img_id
        if (user_id, folder_id, img_id) in self.blobs[sha]['loc']:
          # and we are done for this image, since it is a complete duplicate
          known_count += 1
          logging.info('Image %d already in %s', img_id, self.AlbumStr(user_id, folder_id))
          continue
        # in this last case we know the img_id but it seems to be duplicated in another album,
        # so we have to get the image name at least so we can add it to the database
        try:
          _, sanitized_image_name, _ = fapbase.ExtractFullImageURL(img_id)
          self.blobs[sha]['date'] = base.INT_TIME()
          logging.info('New location added for known image %d (%r)', img_id, sanitized_image_name)
        except fapbase.Error404:
          # image failed, but we can trust to add it with 'unknown' name because the SHA is the same
          logging.warning('Image %d failed to fetch but is being added with name "unknown"', img_id)
        # either way we are done with this image
        self.blobs[sha]['loc'][(user_id, folder_id, img_id)] = (sanitized_image_name, 'new')
        known_count += 1
        continue
      # we don't know about this specific img_id yet: we need more information
      try:
        # get image's full resolution URL + name
        url_path, sanitized_image_name, extension = fapbase.ExtractFullImageURL(img_id)
        # get the binary data so we can compute the SHA for this image
        image_bytes, sha = fapbase.GetBinary(url_path)
      except fapbase.Error404 as err:
        err.image_id = img_id
        err.image_name = sanitized_image_name  # this might be None or this might be filled in
        self.favorites[user_id][folder_id]['images'].remove(img_id)
        self.favorites[user_id][folder_id]['failed_images'].add(err.FailureTuple(log=True))
        failed_count += 1
        logging.error('Image %d failed in %s', img_id, self.AlbumStr(user_id, folder_id))
        continue
      # we now have binary data and a SHA for sure: check if SHA is in DB
      if sha in self.blobs and self.HasBlob(sha):
        # we already have this image, so we just add it to 'loc' and to the index
        self.blobs[sha]['loc'][(user_id, folder_id, img_id)] = (sanitized_image_name, 'new')
        self.blobs[sha]['date'] = base.INT_TIME()
        self.image_ids_index[img_id] = sha
        exists_count += 1
        logging.info('New location added for duplicate image %d (%r)', img_id, sanitized_image_name)
        continue
      # now we know we have a truly new image that needs perceptual hashes, thumbnail, etc
      # create a temporary file so we can do all the clear-text operations we need on the file
      with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        # write the data we already have to the temp file
        temp_file.write(image_bytes)
        temp_file.flush()
        # generate thumbnail and get dimensions and other image info;
        # do this *first* because the extension can change here on PIL's advice
        thumb_sz, width, height, is_animated, extension = self._MakeThumbnailForBlob(
            sha, extension, temp_file)
        total_thumb_sz += thumb_sz
        # write binary data to the final disk destination
        total_sz += self._SaveImage(self._BlobPath(sha, extension_hint=extension), image_bytes)
        # calculate image hashes
        percept_hash, average_hash, diff_hash, wavelet_hash, cnn_hash = self.duplicates.Encode(
            temp_file.name)
        # create blob and index entries
        self.blobs[sha] = {
            'loc': {(user_id, folder_id, img_id): (sanitized_image_name, 'new')},
            'tags': set(), 'sz': len(image_bytes), 'sz_thumb': thumb_sz, 'ext': extension,
            'percept': percept_hash, 'average': average_hash, 'diff': diff_hash,
            'wavelet': wavelet_hash, 'cnn': cnn_hash, 'width': width, 'height': height,
            'animated': is_animated, 'date': base.INT_TIME(), 'gone': {}}
        self.image_ids_index[img_id] = sha
        saved_count += 1
        logging.info('New image %d (%r) finished processing', img_id, sanitized_image_name)
      # temp file is closed; checkpoint database, if needed
      if checkpoint_size and not saved_count % checkpoint_size:
        self.Save()
    # all images were downloaded, the end, log and save
    self.favorites[user_id][folder_id]['date_blobs'] = base.INT_TIME()  # marks album as done
    self.Save()
    print(f'Album {self.AlbumStr(user_id, folder_id)}: '
          f'Saved {saved_count} images to disk ({base.HumanizedBytes(total_sz)}) and '
          f'{base.HumanizedBytes(total_thumb_sz)} in thumbnails; also {known_count} images were '
          f'already in DB and {exists_count} images were already saved to destination, '
          f'and we had {failed_count} image failures')
    return total_sz

  def _MakeThumbnailForBlob(
      self, sha: str,
      extension: str,
      temp_file: tempfile._TemporaryFileWrapper) -> tuple[int, int, int, bool, str]:
    """Make equivalent thumbnail for `sha` entry. Will overwrite destination.

    Args:
      sha: the SHA256 key
      extension: the extension of the original blob (image)
      temp_file: Temporary file, like created with tempfile.NamedTemporaryFile, in saved state,
          so this method can call open it to read the original binary data

    Returns:
      (int size of saved file, original width, original height, is animated image, actual extension)

    Raises:
      Error: if image has inconsistencies
    """
    # open image and generate a thumbnail
    with Image.open(temp_file.name) as img:
      # check that extension (coming from imagefap) matches the perception PIL has of the image
      if img.format is not None:
        fmt = fapbase.NormalizeExtension(img.format)
        if extension != fmt:
          logging.error('Extension is marked %r while PIL identified image as %r', extension, fmt)
          extension = fmt  # change it to what PIL advises
      # figure paths to use
      output_path = self._ThumbnailPath(sha, extension_hint=extension)
      output_prefix, output_name = os.path.split(output_path)
      output_name = f'unencrypted.{output_name}'
      unencrypted_path = os.path.join(output_prefix, output_name)
      try:  # this try block is to ensure `unencrypted_path` gets deleted from disk
        # figure out the new size that will be used
        width, height = img.width, img.height
        is_animated: bool = getattr(img, 'is_animated', False)
        if max((width, height)) <= _THUMBNAIL_MAX_DIMENSION:
          # the image is already smaller than the putative thumbnail: just copy it as thumbnail
          shutil.copyfile(temp_file.name, unencrypted_path)
          logging.info('Copied image as thumbnail for %r', sha)
        else:
          if width > height:
            new_width, factor = _THUMBNAIL_MAX_DIMENSION, width / _THUMBNAIL_MAX_DIMENSION
            new_height = math.floor(height / factor)
          else:
            new_height, factor = _THUMBNAIL_MAX_DIMENSION, height / _THUMBNAIL_MAX_DIMENSION
            new_width = math.floor(width / factor)
          if is_animated and extension == 'gif':
            # special process for animated images, specifically an animated `gif`

            def _thumbnails(img_frames: Iterator[Image.Image]) -> Iterator[Image.Image]:
              for frame in img_frames:
                thumbnail = frame.copy()
                thumbnail.thumbnail((new_width, new_height), Image.LANCZOS)
                yield thumbnail

            frames: Iterator[Image.Image] = _thumbnails(ImageSequence.Iterator(img))
            first_frame = next(frames)   # handle first frame separately: will be used to save
            first_frame.info = img.info  # copy sequence info into first frame
            first_frame.save(unencrypted_path, save_all=True, append_images=list(frames))
            logging.info('Saved animated thumbnail for %r', sha)
          else:
            # simpler process for regular (non-animated) images
            img.thumbnail((new_width, new_height), resample=Image.LANCZOS)
            img.save(unencrypted_path)
            logging.info('Saved thumbnail for %r', sha)
        # we get the size of the created file so we can return it
        sz_thumb = os.path.getsize(unencrypted_path)
        # we now encrypt the temporary file into its final destination (or copy if no encryption)
        if self._key is None:
          shutil.copyfile(unencrypted_path, output_path)
        else:
          with open(unencrypted_path, 'rb') as unencrypted_obj:
            bin_data = unencrypted_obj.read()
          with open(output_path, 'wb') as encrypted_obj:
            encrypted_obj.write(base.Encrypt(bin_data, self._key))
        return (sz_thumb, width, height, is_animated, extension)
      finally:
        # we really have to try to delete the unencrypted file
        if os.path.exists(unencrypted_path):
          os.remove(unencrypted_path)

  def _SaveImage(self, full_path: str, bin_data: bytes) -> int:
    """Save bin_data, the image data, to full_path.

    Args:
      full_path: File path
      bin_data: Image binary data

    Returns:
      number of bytes actually saved
    """
    bin_sz = len(bin_data)
    with open(full_path, 'wb') as file_obj:
      file_obj.write(bin_data if self._key is None else base.Encrypt(bin_data, self._key))
    logging.info('Saved %s for image %r', base.HumanizedBytes(bin_sz), full_path)
    return bin_sz

  def DeleteUserAndAlbums(self, user_id: int) -> tuple[int, int]:
    """Delete an user, together with favorites and orphaned blobs, thumbs, indexes and duplicates.

    Args:
      user_id: User ID

    Returns:
      (number of blobs deleted, number of duplicates deleted)

    Raises:
      Error: invalid user_id or folder_id
    """
    # check input
    if user_id not in self.users:
      raise Error(f'Invalid user {user_id}')
    # delete the favorite albums first
    img_count: int = 0
    duplicate_count: int = 0
    for folder_id in set(self.favorites.get(user_id, {}).keys()):
      img, duplicate = self.DeleteAlbum(user_id, folder_id)
      img_count += img
      duplicate_count += duplicate
    # finally delete the actual user entry and return the counts
    del self.favorites[user_id]
    del self.users[user_id]
    return (img_count, duplicate_count)

  def DeleteAlbum(self, user_id: int, folder_id: int) -> tuple[int, int]:
    """Delete an user favorites album, together with orphaned blobs, thumbs, indexes and duplicates.

    Args:
      user_id: User ID
      folder_id: Folder ID

    Returns:
      (number of blobs deleted, number of duplicates deleted)

    Raises:
      Error: invalid user_id or folder_id or image location entry not found
    """
    # check input
    if user_id not in self.users or user_id not in self.favorites:
      raise Error(f'Invalid user {user_id}')
    if folder_id not in self.favorites[user_id]:
      raise Error(f'Invalid folder {folder_id} for user {self.UserStr(user_id)}')
    # get the album and go through the images deleting as necessary
    img_count: int = 0
    duplicate_count: int = 0
    images: list[int] = self.favorites[user_id][folder_id]['images']
    for img_id in images:
      # get the blob
      sha = self.image_ids_index[img_id]
      # remove the location entry from the blob
      del self.blobs[sha]['loc'][(user_id, folder_id, img_id)]
      # now we either still have locations for this blob, or it is orphaned
      if self.blobs[sha]['loc']:
        # we still have locations using this blob: the blob stays and we might remove index
        self._DeleteIndexIfOrphan(folder_id, img_id)
        continue
      # this blob is orphaned and must be purged; start by deleting the files on disk, if they exist
      duplicate_count += int(self._DeleteOrphanBlob(sha))
      img_count += 1
    # finally delete the actual album entry and return the counts
    del self.favorites[user_id][folder_id]
    return (img_count, duplicate_count)

  def _DeleteOrphanBlob(self, sha: str) -> bool:
    """Delete orphaned blob `sha` and take care of its dependencies.

    Args:
      sha: the blob to delete

    Returns:
      True if a duplicates group was deleted too; False otherwise
    """
    try:
      os.remove(self._BlobPath(sha))
      logging.info('Deleted blob %r from disk', sha)
    except FileNotFoundError as err:
      logging.warning('Blob %r not found: %s', sha, err)
    try:
      os.remove(self._ThumbnailPath(sha))
      logging.info('Deleted thumbnail %r from disk', sha)
    except FileNotFoundError as err:
      logging.warning('Thumbnail %r not found: %s', sha, err)
    # now delete the blob entry
    del self.blobs[sha]
    # purge the duplicates and the indexes associated with this blob
    self._DeleteIndexesToBlob(sha)
    return self.duplicates.TrimDeletedBlob(sha)

  def _DeleteIndexesToBlob(self, sha: str) -> None:
    """Delete all index entries pointing to (recently deleted) blob `sha`."""
    for img in {i for i, s in self.image_ids_index.items() if s == sha}:
      del self.image_ids_index[img]

  def _DeleteIndexIfOrphan(self, folder_id: int, imagefap_image_id: int) -> None:
    """Delete index entry for `imagefap_image_id` IFF no album uses the index."""
    if not any(
        imagefap_image_id in favorite_obj['images'] and fid != folder_id
        for user_obj in self.favorites.values()
        for fid, favorite_obj in user_obj.items()):
      del self.image_ids_index[imagefap_image_id]

  @property
  def _hashes_encodings_map(self) -> duplicates.HashEncodingMapType:
    """A dictionary containing mapping of filenames and corresponding perceptual hashes."""
    return {method: {sha: obj[method] for sha, obj in self.blobs.items()}  # type: ignore
            for method in duplicates.DUPLICATE_HASHES}

  def DeletePendingDuplicates(self) -> tuple[int, int]:
    """Delete pending duplicate images, including all evaluations, verdicts, and indexes.

    Returns:
      (number of deleted groups, number of deleted image entries)
    """
    return self.duplicates.DeletePendingDuplicates()

  def DeleteAllDuplicates(self) -> tuple[int, int]:
    """Delete all duplicate groups, including all evaluations, verdicts, and indexes.

    Returns:
      (number of deleted groups, number of deleted image entries)
    """
    return self.duplicates.DeleteAllDuplicates()

  def FindDuplicates(self) -> int:
    """Find (perceptual) duplicates.

    Returns:
      int count of new individual duplicate images found
    """
    self._IdenticalVerdictsMaintenance()
    return self.duplicates.FindDuplicates(
        self._hashes_encodings_map,
        {sha for sha, blob in self.blobs.items() if blob['animated']},
        self.configs['duplicates_sensitivity_regular'],
        self.configs['duplicates_sensitivity_animated'])

  def _IdenticalVerdictsMaintenance(self):
    """Goes over locations and resets single entries to 'new'."""
    for blob in self.blobs.values():
      if len(blob['loc']) == 1:
        # single verdicts make no sense, so reset to 'new'
        loc_key = tuple(blob['loc'].keys())[0]
        img_name, verdict = blob['loc'][loc_key]
        if verdict != 'new':
          blob['loc'][loc_key] = (img_name, 'new')

  def AlbumIntegrityCheck(self) -> None:
    """Go over user albums in DB and check that all images are accounted for."""
    self._UsersIntegrityCheck()
    all_valid_ids = self._AlbumIdsIntegrityCheck()
    self._CheckForIndexOrphans(all_valid_ids)
    self._CheckLocationIntegrity()
    self._CheckTagsIntegrity()
    self.Save()

  def _UsersIntegrityCheck(self) -> None:
    """Make sure all users in favorites are listed in user database."""
    for user_id in sorted(self.favorites.keys()):
      if user_id not in self.users:
        logging.error('User ID %d in favorites not supported in DB', user_id)
        # we fix by adding the user
        self.AddUserByID(user_id)
        logging.info('Corrected: added user %s', self.UserStr(user_id))
    logging.info('Finished users integrity audit')

  def _AlbumIdsIntegrityCheck(self) -> set[int]:  # noqa: C901
    """Check all images in albums are valid pointers.

    Check that all image IDs in all albums are in index and index points to valid blob and
    make sure no failed images are listed in the index.

    Returns:
      set of all valid IDs in the database
    """
    all_valid_ids: set[int] = set()
    for user_id in sorted(self.favorites.keys()):
      for album_id in sorted(self.favorites[user_id].keys()):
        if not self.favorites[user_id][album_id]['date_blobs']:
          logging.info('Skipping unfinished album %s', self.AlbumStr(user_id, album_id))
          all_valid_ids.update(self.favorites[user_id][album_id]['images'])
          continue
        for img_id in self.favorites[user_id][album_id]['images'].copy():  # copy to allow change
          # first check for case where the ID is not even in the index
          if img_id not in self.image_ids_index:
            logging.error(
                'Image ID %d in %s is not listed in index',
                img_id, self.AlbumStr(user_id, album_id))
            # fix by trying to download the image and adding it to the database
            try:
              sha, blob_data = self._CreateFilesOnDiskAndProposeBlob(user_id, album_id, img_id)
              if sha in self.blobs:
                self.blobs[sha]['loc'].update(blob_data['loc'])  # update 'loc' in existing blob
              else:
                self.blobs[sha] = blob_data  # create a new blob entry
              self.image_ids_index[img_id] = sha
              all_valid_ids.add(img_id)
              logging.info('Corrected: Image %d added to blobs and index', img_id)
            except fapbase.Error404 as err:
              logging.error(
                  'Failed to download/fix image ID %d in %s',
                  img_id, self.AlbumStr(user_id, album_id))
              self.favorites[user_id][album_id]['images'].remove(img_id)
              self.favorites[user_id][album_id]['failed_images'].add(
                  (img_id, err.timestamp, None, err.url))
            continue
          # we found ID in index, so check to see if SHA is in blobs
          sha = self.image_ids_index[img_id]
          if sha not in self.blobs:
            logging.error(
                'Image ID %d in %s translates to SHA %r not listed in blobs',
                img_id, self.AlbumStr(user_id, album_id), sha)
            try:
              new_sha, blob_data = self._CreateFilesOnDiskAndProposeBlob(user_id, album_id, img_id)
              if new_sha == sha:
                self.blobs[sha] = blob_data  # create a new blob entry
                logging.info('Corrected: Image %d added to blobs', img_id)
              else:
                self.favorites[user_id][album_id]['images'].remove(img_id)
                self.favorites[user_id][album_id]['failed_images'].add(
                    (img_id, base.INT_TIME(), blob_data['loc'].popitem()[1][0], None))
                del self.image_ids_index[img_id]
                logging.error(
                    'Failed to fix image %d because of SHA mismatch (got %r, expected %r)',
                    img_id, new_sha, sha)
                continue
            except fapbase.Error404 as err:
              self.favorites[user_id][album_id]['images'].remove(img_id)
              self.favorites[user_id][album_id]['failed_images'].add(
                  (img_id, err.timestamp, None, err.url))
              del self.image_ids_index[img_id]
              logging.error(
                  'Failed to download/fix image ID %d in %s',
                  img_id, self.AlbumStr(user_id, album_id))
              continue
          all_valid_ids.add(img_id)
        for failed_id in sorted(self.favorites[user_id][album_id]['failed_images']):
          img_id = failed_id[0]
          if img_id in self.image_ids_index:
            sha = self.image_ids_index[img_id]
            logging.error(
                'Image ID %d in %s failed list is actually listed in the index as %r',
                img_id, self.AlbumStr(user_id, album_id), sha)
            if sha in self.blobs:
              # in this case we can fix by promoting the image and adding it to the blob entry
              self.favorites[user_id][album_id]['images'].append(img_id)
              self.favorites[user_id][album_id]['failed_images'].remove(failed_id)
              self.blobs[sha]['loc'][(user_id, album_id, img_id)] = (
                  'unknown' if failed_id[2] is None else failed_id[2], 'new')
              all_valid_ids.add(img_id)
              logging.info('Corrected: Image %d moved to album list and added to %r', img_id, sha)
            else:
              # in this case, since we have no blob, we can only fix by deleting from the index
              del self.image_ids_index[img_id]
              logging.info(
                  'Corrected: Image %d removed from index (SHA %r did not exist)', img_id, sha)
    logging.info('Finished album image ID integrity audit')
    return all_valid_ids

  def _CheckForIndexOrphans(self, all_valid_ids: set[int]) -> None:
    """Make sure there is no leftover (orphaned ID) in index from compared to all IDs."""
    all_index_keys = set(self.image_ids_index)
    for img_id in sorted(all_index_keys.difference(all_valid_ids)):
      logging.error('Image ID %d is in index but not listed in any album')
      # we fix by removing from the index
      del self.image_ids_index[img_id]
      logging.info('Corrected: removed index entry for %d', img_id)
    logging.info('Finished index entries integrity audit')

  def _CheckLocationIntegrity(self) -> None:
    """Make sure all 'loc' entries in blobs are for real user/album and known IDs."""
    for sha in sorted(self.blobs.keys()):
      for user_id, album_id, img_id in sorted(self.blobs[sha]['loc'].keys()):
        if (user_id not in self.users or album_id not in self.favorites[user_id] or
            img_id not in self.favorites[user_id][album_id]['images']):
          logging.error('Blob %r has invalid location %d/%d/%d', sha, user_id, album_id, img_id)
          # we fix by removing from 'loc'
          del self.blobs[sha]['loc'][(user_id, album_id, img_id)]
          logging.info('Corrected: deleted invalid location %d/%d/%d', user_id, album_id, img_id)
          # we must make sure to leave a viable blob behind, so we check for that
          if not self.blobs[sha]['loc']:
            self._DeleteOrphanBlob(sha)
            logging.info('Corrected: orphaned blob %r was deleted', sha)
    logging.info('Finished blob location entries integrity audit')

  def _CheckTagsIntegrity(self) -> None:
    """Make sure all 'tags' entries in blobs are for existing tags."""
    all_valid_tags = {k for k, _, _, _ in self.TagsWalk()}
    for sha in sorted(self.blobs.keys()):
      for tag_id in sorted(self.blobs[sha]['tags']):
        if tag_id not in all_valid_tags:
          logging.error('Blob %r has invalid tag %d', sha, tag_id)
          # we fix by removing the offending tag
          self.blobs[sha]['tags'].remove(tag_id)
          logging.info('Corrected: removed tag %d from blob %r', tag_id, sha)
    logging.info('Finished blob tags entries integrity audit')

  def BlobIntegrityCheck(self) -> None:
    """Go over blobs in DB and on disk checking for missing entries on either side.

    This means both checking for blob files that are orphaned (don't have a DB entry) *and*
    checking that all SHA entries in DB have a blob and a thumb files.
    """
    self._SHAOrphanedCheck()
    self._FileOrphanedCheck()

  def _SHAOrphanedCheck(self) -> None:
    """Check that all SHA entries in DB have a blob and a thumb files and sizes are OK."""
    # PHASE 1: Make sure all blobs in DB exist on disk, both as a blob and as a thumbnail
    logging.info('Searching for missing files...')
    missing_sha: set[str] = set()
    missing_count: int = 0
    decrypt_count: int = 0
    size_count: int = 0
    for sha in sorted(self.blobs.keys()):
      # check for files existence
      has_blob, has_thumb = self.HasBlob(sha), self.HasThumbnail(sha)
      if not has_blob or not has_thumb:
        missing_sha.add(sha)
        missing_count += 1
        logging.error(
            'Missing file entry %r: %s\n    %s blob / %s thumbnail',
            sha, self.LocationsStr(self.blobs[sha]['loc']),
            'OK' if has_blob else 'MISSING', 'OK' if has_thumb else 'MISSING')
        continue  # no need to check for sizes here
      # check that files decrypt correctly (no point in having them if they are corrupted)
      try:
        got_blob = len(self.GetBlob(sha))
        got_thumb = len(self.GetThumbnail(sha))
      except base.bin_fernet.InvalidToken:
        missing_sha.add(sha)
        decrypt_count += 1
        logging.error('Decryption error in %r: %s', sha, self.LocationsStr(self.blobs[sha]['loc']))
        continue  # we know this was a problem already
      # check that sizes are precisely as reported in the database
      blob_sz, thumb_sz = self.blobs[sha]['sz'], self.blobs[sha]['sz_thumb']
      if got_blob != blob_sz or got_thumb != thumb_sz:
        missing_sha.add(sha)
        size_count += 1
        logging.error(
            'Inconsistent sizes in %r: %s\n    wanted %s / %s, got %s / %s',
            sha, self.LocationsStr(self.blobs[sha]['loc']),
            base.HumanizedBytes(blob_sz), base.HumanizedBytes(thumb_sz),
            base.HumanizedBytes(got_blob), base.HumanizedBytes(got_thumb))
    logging.warning(
        'Found %d missing or inconsistent blob entries '
        '(%d missing, %d decryption errors, %d size inconsistencies)',
        len(missing_sha), missing_count, decrypt_count, size_count)
    # PHASE 2: fix the entries that are missing
    if missing_sha:
      logging.warning('Starting DOWNLOAD of missing files...')
      corrected_count, failed_count = self._CorrectMissingSHA(missing_sha)
      self.Save()
      logging.warning(
          '%d files were successfully corrected and %d files failed correction',
          corrected_count, failed_count)
    logging.info('Finished missing files audit and correction attempt')

  def _CorrectMissingSHA(self, missing_sha: set[str]) -> tuple[int, int]:
    corrected_count: int = 0
    failed_count: int = 0
    for sha in sorted(missing_sha):
      blob = self.blobs[sha]
      for user_id, album_id, img_id in sorted(blob['loc'].keys()):  # try for all known IDs in 'loc'
        # get the image data afresh
        try:
          computed_sha, blob_data = self._CreateFilesOnDiskAndProposeBlob(user_id, album_id, img_id)
          if sha != computed_sha:
            logging.error('Image %d had SHA mismatch %r versus %r', img_id, sha, computed_sha)
            continue
        except fapbase.Error404:
          logging.error('Image %d for SHA %r failed download', img_id, sha)
          continue
        # update blob, leave 'loc', 'tags' and 'gone' alone
        del blob_data['loc']   # type: ignore
        del blob_data['tags']  # type: ignore
        del blob_data['gone']  # type: ignore
        blob.update(blob_data)
        # this image was downloaded and saved
        corrected_count += 1
        logging.info('Image SHA %r successfully corrected', sha)
        break  # stop as soon as an img_id has worked! (any img_id in 'loc')
      else:
        failed_count += 1
        logging.error('Image SHA %r FAILED to be corrected', sha)
    return (corrected_count, failed_count)

  def _CreateFilesOnDiskAndProposeBlob(
      self, user_id: int, folder_id: int, img_id: int) -> tuple[str, _BlobObjType]:
    """Get an image and create the blob/thumb files on disk. Returns the proposed blob entry.

    Args:
      user_id: User ID
      folder_id: Folder ID
      img_id: Image ID

    Returns:
      (proposed SHA, proposed filled in blob entry dict)

    Raises:
      Error404: on 404 errors
    """
    # get the image data afresh
    url_path, sanitized_image_name, extension = fapbase.ExtractFullImageURL(img_id)  # might 404
    image_bytes, sha = fapbase.GetBinary(url_path)                                   # might 404
    # create a temporary file so we can do all the clear-text operations we need on the file
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
      # write the data we already have to the temp file
      temp_file.write(image_bytes)
      temp_file.flush()
      # generate thumbnail and get dimensions and other image info, save image
      thumb_sz, width, height, is_animated, extension = self._MakeThumbnailForBlob(
          sha, extension, temp_file)
      self._SaveImage(self._BlobPath(sha, extension_hint=extension), image_bytes)
      percept_hash, average_hash, diff_hash, wavelet_hash, cnn_hash = self.duplicates.Encode(
          temp_file.name)
    # update blob, leave 'loc', 'tags' and 'gone' alone
    return (sha, {
        'loc': {(user_id, folder_id, img_id): (sanitized_image_name, 'new')},
        'tags': set(), 'sz': len(image_bytes), 'sz_thumb': thumb_sz, 'ext': extension,
        'percept': percept_hash, 'average': average_hash, 'diff': diff_hash,
        'wavelet': wavelet_hash, 'cnn': cnn_hash, 'width': width, 'height': height,
        'animated': is_animated, 'date': base.INT_TIME(), 'gone': {}})

  def _FileOrphanedCheck(self) -> None:
    """Check for blob files that are orphaned (don't have a DB entry)."""
    # PHASE 1: Make sure all blobs on disk exist as entries in the DB
    logging.info('Searching for orphaned files...')
    orphaned_unencrypted_leftovers: list[tuple[str, str]] = []
    orphaned_blobs: dict[str, tuple[str, str]] = {}
    orphaned_thumbs: dict[str, tuple[str, str]] = {}
    for dir_path, orphaned_obj, search_str in ((self._blobs_dir, orphaned_blobs, 'BLOB'),
                                               (self._thumbs_dir, orphaned_thumbs, 'THUMBNAIL')):
      for _, _, file_names in os.walk(dir_path):
        for file_name in sorted(file_names):
          file_name = file_name.strip()
          if 'unencrypted' in file_name:
            orphaned_unencrypted_leftovers.append((os.path.join(dir_path, file_name), file_name))
            logging.error('Leftover %s file found: %s', search_str, file_name)
            continue  # we already know this file is in the wrong place
          sha = self._SHAFromFileName(file_name)
          if sha not in self.blobs:
            orphaned_obj[sha] = (os.path.join(dir_path, file_name), file_name)
            logging.error('Orphaned %s file found: %s (%s)', search_str, file_name, sha)
        # stop after first directory (we don't want to "os.walk" into any other directory)
        break
    logging.warning('Found %d unencrypted file left-overs', len(orphaned_unencrypted_leftovers))
    logging.warning('Found %d orphaned BLOBs and %d orphaned THUMBNAILs',
                    len(orphaned_blobs), len(orphaned_thumbs))
    # PHASE 2: delete the extra files
    if orphaned_unencrypted_leftovers or orphaned_blobs or orphaned_thumbs:
      logging.warning('Starting DELETION of orphaned files...')
    for file_path, file_name in orphaned_unencrypted_leftovers:
      logging.info('Deleting leftover file %r', file_name)
      os.remove(file_path)
    for orphaned_obj, search_str in ((orphaned_blobs, 'BLOB'), (orphaned_thumbs, 'THUMBNAIL')):
      for sha in sorted(orphaned_obj.keys()):
        file_path, file_name = orphaned_obj[sha]
        logging.info('Deleting %s orphan file %r (%s)', search_str, file_name, sha)
        os.remove(file_path)
    logging.info('Finished orphaned files audit')

  def Audit(self, user_id: int, checkpoint_size: int, force_audit: bool) -> None:  # noqa: C901
    """Audit an user to find any missing images.

    Args:
      user_id: User ID
      checkpoint_size: Commit database to disk every `checkpoint_size` images checked;
          if zero will not checkpoint at all
      force_audit: If True will audit even if recently audited

    Raises:
      Error: invalid user_id or user not finished
    """
    # check if we know the user and they have been finished
    if user_id not in self.users or not self.users[user_id]['date_finished']:
      raise Error(f'Unknown user {user_id} or user not yet finished: before `audit` you must '
                  'finish downloading all images for the user')
    logging.info(
        'Audit for user %s, last finished %s, last audit %s',
        self.UserStr(user_id), base.STD_TIME_STRING(self.users[user_id]['date_finished']),
        base.STD_TIME_STRING(self.users[user_id]['date_audit']))
    logging.info('*NO* checkpoints used (work may be lost!)' if checkpoint_size == 0 else
                 f'Checkpoint DB every {checkpoint_size} downloads')
    # go over the albums and images for each album, in order
    checked_count: int = 0
    problem_count: int = 0
    for folder_id in sorted(self.favorites[user_id].keys()):
      logging.info('Audit folder %s', self.AlbumStr(user_id, folder_id))
      for original_id in self.favorites[user_id][folder_id]['images']:
        # audit this image: get hash and locations; we always audit all known locations of the image
        sha = self.image_ids_index[original_id]
        tm_last = max(
            [self.blobs[sha]['date']] +
            [g[0] for i, g in self.blobs[sha]['gone'].items() if i == original_id])
        if not force_audit and tm_last and (tm_last + AUDIT_MIN_DOWNLOAD_WAIT) > base.INT_TIME():
          logging.info('Image %d (%s) recently audited: SKIP (%s)',
                       original_id, sha, base.STD_TIME_STRING(tm_last))
          continue
        for img_id in sorted({loc[2] for loc in self.blobs[sha]['loc'].keys()}):  # de-dup with set
          # this is one known location of this image, so read the image page
          # we can't use the full-res URL directly because it expires;
          # also, using _FapHTMLRead() here will help pace the audit with pauses
          url: str = fapbase.IMG_URL(img_id)
          try:
            img_html = fapbase.FapHTMLRead(url)
          except fapbase.Error404:
            self.blobs[sha]['gone'][img_id] = (base.INT_TIME(), _FailureLevel.IMAGE_PAGE, url)
            problem_count += 1
            logging.warning('Image %d: ERROR on %r page', img_id, url)
            continue  # stop on first error for this img_id: do not update date
          # we have a page, so extract the full-res URL
          full_res_urls: list[str] = fapbase.FULL_IMAGE.findall(img_html)
          if not full_res_urls:
            self.blobs[sha]['gone'][img_id] = (base.INT_TIME(), _FailureLevel.URL_EXTRACTION, url)
            problem_count += 1
            logging.warning('Image %d: ERROR on %r full-res extraction', img_id, url)
            continue  # stop on first error for this img_id: do not update date
          full_res_url = full_res_urls[0]
          # finally, stream the actual image to make sure it is there, but avoid data transfer:
          # use the requests.get() with streaming to avoid a full download
          # see: https://docs.python-requests.org/en/latest/user/advanced/#body-content-workflow
          with requests.get(full_res_url, stream=True, timeout=None) as bin_request:  # nosec
            # leaving context stops the download, closes connection, after just the header fetch
            if (bin_request.status_code != 200 or
                int(bin_request.headers['Content-Length']) != self.blobs[sha]['sz']):
              self.blobs[sha]['gone'][img_id] = (
                  base.INT_TIME(), _FailureLevel.FULL_RES, full_res_url)
              problem_count += 1
              logging.warning('Image %d: ERROR on binary %r page', img_id, full_res_url)
              continue  # stop on first error for this img_id: do not update date
          # all went well for this img_id, we should also update the date
          self.blobs[sha]['date'] = base.INT_TIME()
        # we finished auditing this blob for all its locations
        if self.blobs[sha]['gone']:
          logging.warning('Image %d (%s) has errors for IDs %r',
                          original_id, sha, set(self.blobs[sha]['gone'].keys()))
        else:
          logging.info('Image %d (%s) is OK', original_id, sha)
        # checkpoint database, if needed
        checked_count += 1
        if checkpoint_size and not checked_count % checkpoint_size:
          self.Save()
    # finished audit, mark user as audited
    self.users[user_id]['date_audit'] = base.INT_TIME()
    self.Save()
    logging.info(
        'Audit for user %s finished, %d images checked, with %d image errors',
        self.UserStr(user_id), checked_count, problem_count)


def GetDatabaseTimestamp(db_path: str = DEFAULT_DB_DIRECTORY) -> int:
  """Get the (int) timestamp that the database file was last modified.

  Args:
    db_path: Directory path where to find the database file (default DEFAULT_DB_DIRECTORY)

  Returns:
    int timestamp (rounded up to minimize chance of collision)

  Raises:
    Error: if database file does not already exist
  """
  db_file = os.path.join(os.path.expanduser(db_path), _DEFAULT_DB_NAME)
  if not os.path.exists(db_file):
    raise Error(f'Database file not found: {db_file!r}')
  return math.ceil(os.path.getmtime(db_file))
