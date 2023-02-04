"""Create your views here."""

# import pdb

from django import http
# from django.shortcuts import render


class SHA256HexDigest:
  """Django path converter for a SHA256 hexadecimal digest (exactly 64 chars of hexadecimal)."""

  regex = r'[0-9a-fA-F]{64}'  # 64 chars of lower or upper-case hexadecimal

  def to_python(self, value: str) -> str:
    """Convert from URL to (python) type."""
    return value.lower()

  def to_url(self, value: str) -> str:
    """Convert from (python) type to URL."""
    return value.lower()


def ServeIndex(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `index` page."""
  return http.HttpResponse('The index is now empty, under construction...')


def ServeUsers(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `users` page."""
  raise http.Http404('not implemented yet!')


def ServeUser(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `user` page."""
  raise http.Http404('not implemented yet!')


def ServeFavorites(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `favorites` page of one `user_id`."""
  raise http.Http404('not implemented yet!')


def ServeFavorite(request: http.HttpRequest, user_id: int, folder_id: int) -> http.HttpResponse:
  """Serve the `favorite` (album) page for an `user_id` and a `folder_id`."""
  raise http.Http404('not implemented yet!')


def ServeTags(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `tags` page."""
  raise http.Http404('not implemented yet!')


def ServeTag(request: http.HttpRequest, tag_id: int) -> http.HttpResponse:
  """Serve the `tag` page for one `tag_id`."""
  raise http.Http404('not implemented yet!')


def ServeBlob(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `blob` page, one image, given one SHA256 `digest`."""
  raise http.Http404('not implemented yet!')


def ServeDuplicates(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `duplicates` page."""
  raise http.Http404('not implemented yet!')


def ServeDuplicate(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `duplicate` page, with a set of duplicates, by giving one of the SHA256 `digest`."""
  raise http.Http404('not implemented yet!')
