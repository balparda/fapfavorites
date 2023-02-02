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


# internal data utils
DUPLICATES_TYPE = dict[tuple[str, ...], dict[str, Literal['new', 'false', 'keep', 'skip']]]


class Duplicates():
  """Stores and manipulates duplicates data."""

  def __init__(self, duplicates_index: DUPLICATES_TYPE):
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

  def _GetSetKey(self, sha: str) -> Optional[tuple[str, ...]]:
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
