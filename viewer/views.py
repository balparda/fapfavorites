"""Create your views here."""

# import pdb

from django import http
from django.template import loader
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
  template = loader.get_template('viewer/index.html')
  context = {
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))


def ServeUsers(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `users` page."""
  template = loader.get_template('viewer/users.html')
  context = {
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))


def ServeUser(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `user` page."""
  template = loader.get_template('viewer/user.html')
  context = {
      'user_id': user_id,
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))


def ServeFavorites(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `favorites` page of one `user_id`."""
  template = loader.get_template('viewer/favorites.html')
  context = {
      'user_id': user_id,
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))


def ServeFavorite(request: http.HttpRequest, user_id: int, folder_id: int) -> http.HttpResponse:
  """Serve the `favorite` (album) page for an `user_id` and a `folder_id`."""
  template = loader.get_template('viewer/favorite.html')
  context = {
      'user_id': user_id,
      'folder_id': folder_id,
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))


def ServeTags(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `tags` page."""
  template = loader.get_template('viewer/tags.html')
  context = {
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))


def ServeTag(request: http.HttpRequest, tag_id: int) -> http.HttpResponse:
  """Serve the `tag` page for one `tag_id`."""
  template = loader.get_template('viewer/tag.html')
  context = {
      'tag_id': tag_id,
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))


def ServeBlob(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `blob` page, one image, given one SHA256 `digest`."""
  raise http.Http404('not implemented yet!')


def ServeDuplicates(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `duplicates` page."""
  template = loader.get_template('viewer/duplicates.html')
  context = {
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))


def ServeDuplicate(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `duplicate` page, with a set of duplicates, by giving one of the SHA256 `digest`."""
  template = loader.get_template('viewer/duplicate.html')
  context = {
      'digest': digest,
      # TODO: fill context with actual data
  }
  return http.HttpResponse(template.render(context, request))
