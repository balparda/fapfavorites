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
"""Imagefap.com duplicates library."""

import logging
# import pdb
from typing import Literal, Optional

from imagededup import methods as image_methods


# internal types definitions

DuplicatesKeyType = tuple[str, ...]
DuplicatesType = dict[DuplicatesKeyType, dict[str, Literal['new', 'false', 'keep', 'skip']]]
DUPLICATE_OPTIONS = {'new', 'false', 'keep', 'skip'}


class Duplicates:
  """Stores and manipulates duplicates data."""

  def __init__(self, duplicates_index: DuplicatesType):
    """Construct.

    Args:
      duplicates_index: The self._duplicates_index from FapDatabase.
    """
    self.index = duplicates_index
    self._perceptual_hasher = image_methods.PHash()

  @property
  def hashes(self) -> set[str]:
    """All sha256 keys that are currently affected by duplicates."""
    all_sha: set[str] = set()
    for sha_tuple in self.index.keys():
      all_sha.update(sha_tuple)
    return all_sha

  def _GetSetKey(self, sha: str) -> Optional[DuplicatesKeyType]:
    """Find and return the key containing `sha`, or None if not found."""
    for k in self.index.keys():
      if sha in k:
        return k
    return None

  def Encode(self, image_path: str) -> str:
    """Get perceptual hash for one specific image in image_path."""
    return self._perceptual_hasher.encode_image(image_file=image_path)

  def AddDuplicateSet(self, sha_set: set[str]) -> int:
    """Add a new duplicate set to the collection.

    Args:
      sha_set: The set of sha256 to add

    Returns:
      Number of *NEW* sha256 added (the ones marked as 'new' in the database)
    """
    # first we try to find our keys in the existing index
    for sha in sha_set:
      key = self._GetSetKey(sha)
      if key is not None:
        # this is the key to use, for the whole sha_set!
        new_sha_set = sha_set.union(key)
        diff_sha_set = new_sha_set.difference(key)
        if not diff_sha_set:
          return 0  # there is no new sha entry in sha_set
        # we have new entries, so first we create a new dict entry and delete the previous one
        new_sha_key = tuple(sorted(new_sha_set))
        self.index[new_sha_key] = self.index[key]
        del self.index[key]
        # now we add the new duplicates to the old entries
        for k in diff_sha_set:
          self.index[new_sha_key][k] = 'new'
        return len(diff_sha_set)
    # there is no entry that matches any duplicate, so this is all new to us
    self.index[tuple(sorted(sha_set))] = {sha: 'new' for sha in sha_set}
    return len(sha_set)

  def FindDuplicates(self, perceptual_hashes_map: dict[str, str]) -> None:
    """Find (perceptual) duplicates.

    Returns:
      dict of {sha: set_of_other_sha_duplicates}
    """
    logging.info('Searching for perceptual duplicates in database...')
    duplicates: dict[str, list[str]] = self._perceptual_hasher.find_duplicates(
        encoding_map=perceptual_hashes_map)
    filtered_duplicates = {k: set(d) for k, d in duplicates.items() if d}
    new_duplicates = 0
    for sha, sha_set in filtered_duplicates.items():
      new_duplicates += self.AddDuplicateSet(sha_set.union({sha}))
    logging.info(
        'Found %d new perceptual duplicates in %d groups, '
        'database has %d images marked as duplicates',
        new_duplicates, len(self.index), len(self.hashes))

  def TrimDeletedBlob(self, sha: str) -> int:
    """Find duplicates depending a (newly deleted) blob and remove them from database.

    Note that if a key was removed from a duplicate set but the group still remained based
    on images that were not deleted, we have (for safety/consistency's sake) to reset that
    duplicate group to all 'new'. The only exception is for false positives ('false') as
    those can presumably be left alone. Any other action/assumption would risk horrible bugs.
    In summary 'new'|'false'-> left alone ; 'keep'|'skip' -> reset to 'new'.

    Args:
      sha: The recently deleted sha256 to trim from duplicates database

    Returns:
      Number of duplicate groups that were entirely deleted; note that this does NOT include
      duplicates that were trimmed of a key but still had >=2 images in set so were kept
    """
    deleted_groups = 0
    for sha_tuple in set(self.index.keys()):
      if sha in sha_tuple:
        # hit! we have to figure something out
        if len(sha_tuple) <= 2:
          # easy deletion case: there is no duplicate with only 1 key, so purge
          del self.index[sha_tuple]
          deleted_groups += 1
          logging.info('Deleted duplicate entry %r', sha_tuple)
          continue
        # this is a group with more than 2 keys, so care must be taken; first delete the sha entry
        del self.index[sha_tuple][sha]
        # now reset the status of the remaining keys that are not 'new' or 'false'
        for k in {k for k, d in self.index[sha_tuple].items() if d in {'keep', 'skip'}}:
          self.index[sha_tuple][k] = 'new'
        # finally move the entry to a new clean key entry with only the remaining sha digests
        new_sha_key = tuple(sorted(self.index[sha_tuple].keys()))
        self.index[new_sha_key] = self.index[sha_tuple]
        del self.index[sha_tuple]
    # finished, return the count
    return deleted_groups
