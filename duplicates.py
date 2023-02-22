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
"""Imagefap.com duplicates library.

Largely based on imagededup package, see: https://idealo.github.io/imagededup/
"""

import logging
# import pdb
from typing import Literal, Optional, Union, TypedDict

from imagededup import methods as image_methods
import numpy as np

from baselib import base


# internal types definitions

DuplicatesKeyType = tuple[str, ...]

DuplicatesVerdictType = Literal['new', 'false', 'keep', 'skip']
DUPLICATE_OPTIONS: set[DuplicatesVerdictType] = {'new', 'false', 'keep', 'skip'}

DuplicatesHashType = Literal['percept', 'average', 'diff', 'wavelet', 'cnn']
DUPLICATE_HASHES: tuple[DuplicatesHashType, ...] = ('percept', 'average', 'diff', 'wavelet', 'cnn')


class _SensitivitiesType(TypedDict):
  """Image dup hasher objects type."""

  percept: int
  average: int
  diff: int
  wavelet: int
  cnn: float


METHOD_SENSITIVITY_DEFAULTS: _SensitivitiesType = {
    # if you change the defaults here, remember to change them in duplicates.html & README.md
    'percept': 4,  # max hamming distance considered a duplicate (library default =10)
    'diff': 4,     # max hamming distance considered a duplicate (library default =10)
    'average': 1,  # max hamming distance considered a duplicate (library default =10)
    'wavelet': 1,  # max hamming distance considered a duplicate (library default =10)
    'cnn': 0.95,   # min cosine similarity threshold considered a duplicate (library default =0.9)
}
ANIMATED_SENSITIVITY_DEFAULTS: _SensitivitiesType = {
    # if you change the defaults here, remember to change them in duplicates.html & README.md
    'percept': 3,
    'diff': 1,
    'average': -1,  # deactivated
    'wavelet': -1,  # deactivated
    'cnn': 0.97,
}


class DuplicateObjType(TypedDict):
  """Duplicate object type."""

  sources: dict[DuplicatesHashType, dict[DuplicatesKeyType, Union[int, float]]]
  verdicts: dict[str, DuplicatesVerdictType]


class HasherObjType(TypedDict):
  """Image dup hasher objects type."""

  percept: image_methods.PHash
  average: image_methods.AHash
  diff: image_methods.DHash
  wavelet: image_methods.WHash
  cnn: image_methods.CNN


class HashEncodingMapType(TypedDict):
  """Hash encodings type."""

  percept: dict[str, str]
  average: dict[str, str]
  diff: dict[str, str]
  wavelet: dict[str, str]
  cnn: dict[str, np.ndarray]


DuplicatesType = dict[DuplicatesKeyType, DuplicateObjType]
DuplicatesKeyIndexType = dict[str, DuplicatesKeyType]


class Error(base.Error):
  """Base duplicates exception."""


class Duplicates:
  """Stores and manipulates duplicates data."""

  def __init__(
      self, duplicates_registry: DuplicatesType, duplicates_key_index: DuplicatesKeyIndexType):
    """Construct.

    Args:
      duplicates_registry: The registry (self._db['duplicates_registry']) from FapDatabase.
      duplicates_key_index: The index (self._db['duplicates_key_index']) from FapDatabase.
    """
    self.registry = duplicates_registry
    self.index = duplicates_key_index
    # don't create and store all the hasher object beforehand because the CNN will need to expand
    # users, create directories, and will be some time loading (noticeable fractions of seconds);
    # we won't need them all the time, the django site doesn't need them (yet), etc
    self._lazy_perceptual_hashers: Optional[HasherObjType] = None

  @property
  def perceptual_hashers(self) -> HasherObjType:
    """Gets the constructed perceptual hashers (HasherObjType). Lazy construction."""
    if self._lazy_perceptual_hashers is None:
      self._lazy_perceptual_hashers = {
          'percept': image_methods.PHash(),
          'average': image_methods.AHash(),
          'diff': image_methods.DHash(),
          'wavelet': image_methods.WHash(),
          'cnn': image_methods.CNN(),
          # CNN creation will need to expand users, create directories, and will be some
          # time loading (noticeable fractions of seconds)
      }
    return self._lazy_perceptual_hashers

  def Encode(self, image_path: str) -> tuple[str, str, str, str, np.ndarray]:
    """Get perceptual hash for one specific image in image_path.

    Args:
      image_path: The full image path to get the image from

    Returns:
      (percept_hash, average_hash, diff_hash, wavelet_hash, cnn_hash)
    """
    return tuple(  # type: ignore
        self.perceptual_hashers[method].encode_image(image_file=image_path)[0]
        if method == 'cnn' else
        self.perceptual_hashers[method].encode_image(image_file=image_path)
        for method in DUPLICATE_HASHES)

  def AddDuplicatePair(  # noqa: C901
      self, sha1: str, sha2: str, score: Union[int, float], method: DuplicatesHashType) -> int:
    """Add a new duplicate pair relationship to the collection.

    Args:
      sha1: The first SHA256
      sha2: The second SHA256
      score: The relationship score
      method: The method used to unearth the relationship

    Returns:
      Number of *NEW* sha256 added (the ones marked as 'new' in the database)
    """
    # first we try to find our keys in the existing index: make sure to gather all affected keys
    dup_keys: set[DuplicatesKeyType] = set()
    sha_set = {sha1, sha2}
    for sha in sha_set:
      if sha in self.index:
        dup_keys.add(self.index[sha])
    # maybe we found nothing, so these keys are all new to us, which is an easy case
    new_key: DuplicatesKeyType = tuple()
    added_count: int = 0
    if not dup_keys:
      new_key: DuplicatesKeyType = tuple(sorted(sha_set))
      self.registry[new_key] = {
          'sources': {method: {new_key: score}},
          'verdicts': {sha1: 'new', sha2: 'new'},
      }
      added_count = 2
    # maybe this is all related to exactly one existing duplicates group
    elif len(dup_keys) == 1:
      # compose a new key, find out the diff to the old one
      old_key = dup_keys.pop()
      new_key: DuplicatesKeyType = tuple(sorted(sha_set.union(old_key)))
      diff_sha_set = set(new_key).difference(old_key)
      added_count = len(diff_sha_set)  # can be only 0 or 1
      # we only have to move the entry where there is some diff
      if diff_sha_set:
        # move the entry to the new key, delete at old position, we keep the old verdicts
        self.registry[new_key] = self.registry[old_key]
        del self.registry[old_key]
        # now we add the new duplicate sha to the new key position
        new_sha = diff_sha_set.pop()
        if diff_sha_set:
          raise Error('SHA remained where none should be: %r/%r, %r' % (sha1, sha2, diff_sha_set))
        self.registry[new_key]['verdicts'][new_sha] = 'new'
      # now that the key is OK, add the new score
      self.registry[new_key]['sources'].setdefault(method, {})[tuple(sorted(sha_set))] = score
    # final possible case is that we have 2 separate groups that we must merge
    elif len(dup_keys) == 2:
      # compose a new key
      old_key_set: set[str] = set()
      for dup_key in dup_keys:
        old_key_set = old_key_set.union(dup_key)
      new_key: DuplicatesKeyType = tuple(sorted(sha_set.union(old_key_set)))
      added_count = 0
      if set(new_key).difference(old_key_set):
        raise Error('Merging still had inserted keys: %r/%r, %r' % (sha1, sha2, dup_keys))
      # not a good idea to try to keep old verdicts, so the new super-group will be reset to 'new'
      self.registry[new_key] = {'sources': {}, 'verdicts': {sha: 'new' for sha in new_key}}
      # copy sources from old locations and then delete old entries, finishing the merge
      for dup_key in dup_keys:
        for old_method, old_scores in self.registry[dup_key]['sources'].items():
          for pair_key, old_score in old_scores.items():
            self.registry[new_key]['sources'].setdefault(old_method, {})[pair_key] = old_score
        del self.registry[dup_key]
      # now that the merge is complete and all old sources are copied, add the new score
      self.registry[new_key]['sources'].setdefault(method, {})[tuple(sorted(sha_set))] = score
    else:
      raise Error('Unexpected duplicate keys length: %r/%r, %r' % (sha1, sha2, dup_keys))
    # now we update the index (make sure to overwrite all sha in new_key!), and return the count
    for sha in new_key:
      self.index[sha] = new_key
    return added_count

  def DeleteAllDuplicates(self) -> tuple[int, int]:
    """Delete all duplicate groups, including all evaluations, verdicts, and indexes.

    Returns:
      (number of deleted groups, number of deleted image entries)
    """
    # TODO: implement a "delete pending duplicates" that will delete only the "new"; the idea
    #     is that a user can recompute the duplicates (maybe with different parameters) without
    #     losing the skip/keep work that was done; this also implies that the groups won't get
    #     so aggressively reset like they are today
    # first delete the registry
    n_dup = len(self.registry)
    n_img: int = 0
    for dup_keys in list(self.registry.keys()):
      n_img += len(dup_keys)
      del self.registry[dup_keys]
    # then delete the index
    for sha in list(self.index.keys()):
      del self.index[sha]
    return (n_dup, n_img)

  def FindDuplicates(  # noqa: C901
      self,
      hash_encodings_map: HashEncodingMapType,
      animated_keys: set[str],
      regular_sensitivities: _SensitivitiesType,
      animated_sensitivities: _SensitivitiesType) -> int:
    """Find (perceptual) duplicates and add them to the DB.

    Args:
      hash_encodings_map: dict like {method: {sha: encoding}}, see:
          https://idealo.github.io/imagededup/user_guide/finding_duplicates/
      regular_sensitivities: dict (like _SensitivitiesType) with values to use for the sensitivities
          targeted to regular images
      animated_sensitivities: dict (like _SensitivitiesType) with values to use for the
          sensitivities targeted to animated images

    Returns:
      int count of new individual duplicate images found
    """
    # double check that animated criteria is strictly stricter than regular,
    # or the algorithm used below won't work correctly
    for method in DUPLICATE_HASHES:
      if method == 'cnn':
        if (animated_sensitivities['cnn'] < regular_sensitivities['cnn'] and
            animated_sensitivities['cnn'] != -1.0):
          raise Error(
              'Animated sensitivity (method \'CNN\') must be stricter than regular one (%f < %f)' %
              (animated_sensitivities['cnn'], regular_sensitivities['cnn']))
      else:
        if animated_sensitivities[method] > regular_sensitivities[method]:
          raise Error(
              'Animated sensitivity (method %r) must be stricter than regular one (%d > %d)' %
              (method.upper(), animated_sensitivities[method], regular_sensitivities[method]))
    # do the scoring by method
    logging.info('Searching for perceptual duplicates in database...')
    new_duplicates: int = 0
    for method in DUPLICATE_HASHES:
      # for each method, we get all the duplicates and scores
      if method == 'cnn':
        if regular_sensitivities['cnn'] < 0.0:
          logging.warning('Duplicate method \'CNN\' disabled: SKIP')
          continue
        logging.info(
            'Computing diffs using \'CNN\', with threshold >=%0.2f and animated>=%0.2f',
            regular_sensitivities['cnn'], animated_sensitivities['cnn'])
        method_dup: dict[str, list[tuple[str, Union[int, float]]]] = (
            self.perceptual_hashers[method].find_duplicates(
                encoding_map=hash_encodings_map[method],  # type: ignore
                min_similarity_threshold=regular_sensitivities['cnn'],
                scores=True))
      else:
        if regular_sensitivities[method] < 0:
          logging.warning('Duplicate method %r disabled: SKIP', method.upper())
          continue
        logging.info(
            'Computing diffs using %r, with regular threshold <=%d and animated <=%d',
            method.upper(), regular_sensitivities[method], animated_sensitivities[method])
        method_dup: dict[str, list[tuple[str, Union[int, float]]]] = (
            self.perceptual_hashers[method].find_duplicates(
                encoding_map=hash_encodings_map[method],
                max_distance_threshold=regular_sensitivities[method],
                scores=True))
      # we filter them into pairs of duplicates and a score, eliminating symmetric relationships
      scored_duplicates: dict[DuplicatesKeyType, Union[int, float]] = {}
      for sha1, dup in method_dup.items():
        if dup:
          for sha2, score in dup:
            # if these are animated images we use alternate scoring that *MUST* be stricter than
            # the regular scores
            if sha1 in animated_keys or sha2 in animated_keys:
              if method == 'cnn':
                if score < animated_sensitivities['cnn']:
                  continue
              else:
                if score > animated_sensitivities[method]:
                  continue
            # still here? this is a valid pair, so store it
            dup_key: DuplicatesKeyType = tuple(sorted({sha1, sha2}))
            if dup_key in scored_duplicates and scored_duplicates[dup_key] != score:
              raise Error('Duplicate collision, method %r, key %r, new score %d versus %d' % (
                  method, dup_key, score, scored_duplicates[dup_key]))
            scored_duplicates[dup_key] = score
      # now we add each de-duplicated pair to the database
      for (sha1, sha2), score in scored_duplicates.items():
        new_duplicates += self.AddDuplicatePair(sha1, sha2, score, method)
    # finished, log and return all new duplicates found
    logging.info(
        'Found %d new perceptual duplicate individual images; '
        'Currently DB has %d images marked as duplicates, lumped in %d groups',
        new_duplicates, len(self.index), len(self.registry))
    return new_duplicates

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
    del self.registry[old_key]['verdicts'][sha]
    # traverse the scores and delete all that contained `sha`
    for method in set(self.registry[old_key]['sources'].keys()):
      scores = self.registry[old_key]['sources'][method]
      for key_pair in set(scores.keys()):
        if sha in key_pair:
          del scores[key_pair]
      # remember to wipe out empty method entries
      if not scores:
        del self.registry[old_key]['sources'][method]
    # now reset the status of the remaining keys that are not 'new' or 'false'
    for k in {k for k, d in self.registry[old_key]['verdicts'].items() if d in {'keep', 'skip'}}:
      self.registry[old_key]['verdicts'][k] = 'new'
    # finally move the entry to a new clean key entry with only the remaining digests
    new_key: DuplicatesKeyType = tuple(sorted(remaining_digests))
    self.registry[new_key] = self.registry[old_key]
    del self.registry[old_key]
    # remember to point the indexes to the new key too
    for k in remaining_digests:
      self.index[k] = new_key
    return False
