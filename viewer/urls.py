"""Manages URL mapping."""

from django import urls

from . import views


urls.register_converter(views.SHA256HexDigest, 'sha256')


urlpatterns = [

    # index
    urls.path('', views.ServeIndex, name='index'),

    # the users
    urls.path('users/', views.ServeUsers, name='users'),

    # the favorites
    urls.path('favorites/<int:user_id>/', views.ServeFavorites, name='favorites'),
    urls.path('favorite/<int:user_id>/<int:folder_id>/', views.ServeFavorite, name='favorite'),

    # the tags
    urls.path('tag/<int:tag_id>/', views.ServeTag, name='tag'),

    # the blobs and thumbnails
    urls.path('blob/<sha256:digest>/', views.ServeBlob, name='blob'),
    urls.path('thumb/<sha256:digest>/', views.ServeThumb, name='thumb'),

    # the duplicates
    urls.path('duplicates/', views.ServeDuplicates, name='duplicates'),
    urls.path('duplicate/<sha256:digest>/', views.ServeDuplicate, name='duplicate'),

]
