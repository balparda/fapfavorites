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
from typing import Literal

from imagededup import methods as image_methods

from baselib import base


# internal types definitions

DuplicatesKeyType = tuple[str, ...]
DuplicatesVerdictType = Literal['new', 'false', 'keep', 'skip']
DuplicatesType = dict[DuplicatesKeyType, dict[str, DuplicatesVerdictType]]
DUPLICATE_OPTIONS = {'new', 'false', 'keep', 'skip'}
DuplicatesKeyIndexType = dict[str, DuplicatesKeyType]


class Error(base.Error):
  """Base duplicates exception."""


class Duplicates:
  """Stores and manipulates duplicates data."""

  def __init__(
      self, duplicates_registry: DuplicatesType, duplicates_key_index: DuplicatesKeyIndexType):
    """Construct.

    Args:
      duplicates_registry: The self.duplicates (self._db['duplicates_registry']) from FapDatabase.
    """
    self.registry = duplicates_registry
    self.index = duplicates_key_index
    self._perceptual_hasher = image_methods.PHash()

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
    # first we try to find our keys in the existing index: make sure to gather all affected keys
    dup_keys: set[DuplicatesKeyType] = set()
    for sha in sha_set:
      if sha in self.index:
        dup_keys.add(self.index[sha])
    # maybe we found nothing, so these keys are all new to us, which is an easy case
    new_key: DuplicatesKeyType = tuple()
    added_count: int = 0
    if not dup_keys:
      new_key: DuplicatesKeyType = tuple(sorted(sha_set))
      self.registry[new_key] = {sha: 'new' for sha in sha_set}
      added_count = len(sha_set)
    # maybe this is all related to exactly one existing duplicates group
    elif len(dup_keys) == 1:
      # compose a new key, find out the diff to the old one
      old_key = dup_keys.pop()
      new_key: DuplicatesKeyType = tuple(sorted(sha_set.union(old_key)))
      diff_sha_set = set(new_key).difference(old_key)
      added_count = len(diff_sha_set)
      # we only have to act where there is some diff (otherwise we already incorporated all keys)
      if diff_sha_set:
        # move the entry to the new key, delete at old position, we keep the old verdicts
        self.registry[new_key] = self.registry[old_key]
        del self.registry[old_key]
        # now we add the new duplicate sha to the new key position
        for sha in diff_sha_set:
          self.registry[new_key][sha] = 'new'
    # final possible case is that we have multiple separate groups
    else:
      # compose a new key
      old_key_set: set[str] = set()
      for dup_key in dup_keys:
        old_key_set = old_key_set.union(dup_key)
        # we can delete these entries, as we won't be using the old verdicts
        del self.registry[dup_key]
      new_key: DuplicatesKeyType = tuple(sorted(sha_set.union(old_key_set)))
      added_count = len(set(new_key).difference(old_key_set))
      # not a good idea to try to keep old verdicts, so the new super-group will be reset to 'new'
      self.registry[new_key] = {sha: 'new' for sha in new_key}
    # now we update the index (make sure to overwrite all sha in new_key!), and return the count
    for sha in new_key:
      self.index[sha] = new_key
    return added_count

  def FindDuplicates(self, perceptual_hashes_map: dict[str, str]) -> None:
    """Find (perceptual) duplicates.

    Returns:
      dict of {sha: set_of_other_sha_duplicates}
    """
    logging.info('Searching for perceptual duplicates in database...')
    duplicates: dict[str, list[str]] = self._perceptual_hasher.find_duplicates(
        encoding_map=perceptual_hashes_map)
    filtered_duplicates = {k: set(d) for k, d in duplicates.items() if d}
    new_duplicates: int = 0
    for sha, sha_set in filtered_duplicates.items():
      new_duplicates += self.AddDuplicateSet(sha_set.union({sha}))
    logging.info(
        'Found %d new perceptual duplicates; '
        'Currently DB has %d images marked as duplicates, lumped in %d groups',
        new_duplicates, len(self.index), len(self.registry))

  def TrimDeletedBlob(self, sha: str) -> bool:
    """Find duplicates depending a (newly deleted) blob and remove them from database.

    Note that if a key was removed from a duplicate set but the group still remained, based
    on images that were not deleted, we have (for safety/consistency's sake) to reset that
    duplicate group to all 'new'. The only exception is for false positives ('false') as
    those can presumably be left alone. Any other action/assumption would risk horrible bugs.
    In summary 'new'|'false'-> left alone ; 'keep'|'skip' -> reset to 'new'.

    Args:
      sha: The recently deleted sha256 to trim from duplicates database

    Returns:
      True if the group was deleted entirely; False if group still remains, or no duplicate found

    Raises:
      Error: if an inconsistent state is reached (i.e., should not happen)
    """
    # easy case: the digest has no duplicate
    if sha not in self.index:
      return False
    # now we know we have an affected group: get key and remove `sha` index entry
    old_key = self.index.pop(sha)
    remaining_digests = set(old_key).difference({sha})
    if not remaining_digests:
      raise Error('Found duplicate key with less than 2 entries? %r/%s' % (old_key, sha))
    if len(remaining_digests) == 1:
      # easy deletion case: there is no duplicate with only 1 key, so purge the whole group
      del self.registry[old_key]
      del self.index[remaining_digests.pop()]  # remember to remove the other index entry too
      logging.info('Deleted duplicate entry %r', old_key)
      return True
    # this is a group that had more than 2 keys; first delete the `sha` entry inside the object
    del self.registry[old_key][sha]
    # now reset the status of the remaining keys that are not 'new' or 'false'
    for k in {k for k, d in self.registry[old_key].items() if d in {'keep', 'skip'}}:
      self.registry[old_key][k] = 'new'
    # finally move the entry to a new clean key entry with only the remaining digests
    new_key: DuplicatesKeyType = tuple(sorted(remaining_digests))
    self.registry[new_key] = self.registry[old_key]
    del self.registry[old_key]
    # remember to point the indexes to the new key too
    for k in remaining_digests:
      self.index[k] = new_key
    return False
