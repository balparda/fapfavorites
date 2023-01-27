# Imagefap Favorites

Python code that downloads an entire Imagefap favorites image
(picture folder) collection, de-duplicates, and helps organize them.

Started in January/2023, by Daniel Balparda.

## License

Copyright (C) 2023 Daniel Balparda (balparda@gmail.com).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/gpl-3.0.txt.

## Setup

Just the basics, plus a few Python 3 packages, and Balparda's base library.
See below:

```
$ git clone https://github.com/balparda/baselib.git
$ git clone https://github.com/balparda/imagefap-favorites.git
$ sudo apt-get install python3-pip pylint3
$ sudo pip3 install -U click sanitize_filename
```

## Usage

Run `./imagefap-favorites.py --help` for an options and flag summary.

### `get_favorites.py GET` command - _Simple Save of Favorite Images Gallery_

The basic download command is `get`. Use it if you know the user ID
(or user name), picture folder ID (or picture folder name),
and want those saved to a given (or default) output directory.
We can't yet properly deal with HTML
escaping names, so be aware of this. In the absence
of an explicit directory, will default to `~/Downloads/imagefap/`.
This command defaults to preserving file names and just straight
saving them to disk instead of saving them as blobs. It will create
a simple database file that, if kept in the directory, will avoid
having to do repeated work for known images. (You can disable the
database file creation with the `--no-db` option.)
If you use the database you will save a lot of time for repeated
uses or if your connection is broken. The system will remember
the images you have (and skip them) and will remember the pages that
were already seen (a huge difference for very big albums).
You do ___not___ have to worry about missing images because the
duplicate detection here uses `sha256` and will thus _only_ skip files
that are _exactly the same_. No possible mistake here.

This example will find the user _"dirty999"_ and the favorite
gallery _"my pics"_ and download all images to the default directory
(`~/Downloads/imagefap/`). The names are case insensitive and the
script will figure out the correct casing as it loads the IDs:

```
./imagefap-favorites.py get --user dirty999 --folder "my pics"
```

This example will get folder 5678 of user 1234 and place them in
the given directory `~/some-dir/`:

```
./imagefap-favorites.py get --id 1234 --folder 5678 --output "~/some-dir/"
```

If you use the `get` command with multiple favorite galleries and
leave all of them to be saved to the same output directory (either
default or some explicit other one), then exact duplicate images
(again by `sha256`) will ___not___ be saved twice, and the file
name will be the one give for the first time it was saved.

### `get_favorites.py READ` command - _Feed the Database!_

This `read` command is for when you want to do more than just download
images from one (or a few) galleries. This will store the images as blobs
and will feed the database with data. It is _not_ meant for immediate
consumption. The idea is to later run the advanced de-dup on them,
and/or tag them, and/or re-export them in some other fashion.

_(For now the mentioned "advanced" features are only planned and not
implemented, so this option has limited use, but it is important
to document.)_

This example will find the user _"dirty999"_ and the favorite
gallery _"my pics"_ and read all images into the database in
the default directory (`~/Downloads/imagefap/`). The flags behave
the same as for the `get` command:

```
./imagefap-favorites.py read --user dirty999 --folder "my pics"
```

For the `read` command you may instruct it to find all favorite
image galleries in the user's favorite:

```
./imagefap-favorites.py read --user dirty999
```

## Storage

___You don't need to read this section unless you are a developer
for this utility.___

### Default Storage (`get` command)

If no conflicting options are provided, the following storage of
files will be adopted for the `get` operation:

```
~/                                       ==> User root dir
~/Downloads/imagefap/                    ==> App root dir
~/Downloads/imagefap/imagefap.database   ==> serialized metadata file (see below)
~/Downloads/imagefap/original-sanitized-name-1.jpg   ==> image
~/Downloads/imagefap/original-sanitized-name-2.gif   ==> image
```

### Database Storage (`read` command)

If no conflicting options are provided, the following storage of
files will be adopted (`read` command), with the objective of
facilitating image tagging and re-organizing:

```
~/                                       ==> User root dir
~/Downloads/imagefap/                    ==> App root dir
~/Downloads/imagefap/imagefap.database   ==> serialized metadata file (see below)
~/Downloads/imagefap/blobs/              ==> raw images storage directory
~/Downloads/imagefap/blobs/ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb.jpg  ==> blob
~/Downloads/imagefap/blobs/3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d.gif  ==> blob
[... etc ... each blob is:]
~/Downloads/imagefap/blobs/[file_sha_256_hex_digest].[jpg|gif|... original type]
```

### Database Schema

If allowed, will save a database of Imagefap files so we don't have to
hit the servers multiple times. The data will be serialized (pickled)
from a structure like:

```
{

  'users': {
    # stores the seen users
    user_id: user_name
  }

  'favorites': {
    # stores the downloaded picture folders metadata
    user_id: {
      folder_id: {
        'name': folder_name,
        'pages': max_pages_found,
        'images': [imagefap_image_id-1, imagefap_image_id-2, ...],  # in order
      }
    }
  }

  'tags': {
    # stores the user-defined tags for later image re-shuffle
    tag_id: {
      'name': tag_name,
      'type': 'u'|'g'|'c',  # 'u' for user name; 'g' for gallery name; 'c' for custom (user defined)
      'tags': {}  # None, or a nested dict of sub-tags, just like the top one
    }
  }

  'blobs': {
    # stored blob metadata: where has each blob been seen and what tags have been attached
    file_sha_256_hex_digest: {
      'loc': {
        (imagefap_image_id-1, imagefap_full_res_url-1, imagefap_file_name_sanitized-1, user_id-1, folder_id-1),
        (imagefap_image_id-2, imagefap_full_res_url-2, imagefap_file_name_sanitized-2, user_id-2, folder_id-2),
        ... this is a set of every occurrence of the blob in the downloaded favorites ...
      }
      'tags': {tag_id-1, tag_id-2, ...}
    }
  }
  'image_ids_index': {
    # this is a reverse index for 'blobs' so we can easily search by imagefap_image_id
    imagefap_image_id: file_sha_256_hex_digest
  }

}
```

When compressed this structure takes less space than would seem at a first
glance, especially taking into account that it is stored compressed, and
has shown to be a minimal fraction compared to the downloaded images size.
