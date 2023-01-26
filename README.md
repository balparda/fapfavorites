# Imagefap Favorites

Python code that downloads an entire Imagefap favorites image
(picture folder) collection, de-dups, and helps organize them.

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

Just the basic, plus `click` Python 3 packages, and Balparda's base lib:

```
$ git clone https://github.com/balparda/imagefap-favorites.git
$ sudo apt-get install python3-pip pylint3
$ sudo pip3 install -U click sanitize_filename
```

## Usage

Run `./imagefap-favorites.py --help` for an options and flag summary.

For now, just the basic download (`get`) if you know the user ID,
picture folder ID, and give it an output directory.

```
./imagefap-favorites.py get --id 1234 --folder 5678 --output "~/somedir/"
```

Many more features to come. Just laying the groundwork for now.

## Storage Schema

___You don't need to read this section unless you are a developer
for this utility.___

### Default Storage

If no conflicting options are provided, the following storage of
files will be adopted, with the objective of facilitating image
tagging and re-organizing for re-upload:

```
~/                                       ==> User root dir
~/Documents/imagefap/                    ==> App root dir
~/Documents/imagefap/imagefap.database   ==> serialized metadadata file (see below)
~/Documents/imagefap/blobs/              ==> raw images storage directory
~/Documents/imagefap/blobs/ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb.jpg  ==> blob
~/Documents/imagefap/blobs/3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d.gif  ==> blob
[... etc ... each blob is:]
~/Documents/imagefap/blobs/[file_sha_256_hexdigest].[jpg|gif|... original type]
```

### Database

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
        'images': [imagefap_image_id-1, imagefap_image_id-2, ...],  # in order
      }
    }
  }

  'tags': {
    # stores the user-defined tags for later image re-shuffle
    tag_id: {
      'name': tag_name,
      'tags': {}  # None, or a nested dict of sub-tags, just like the top one
    }
  }

  'blobs': {
    # stored blob metadata: where has each blob been seen and what tags have been attached
    file_sha_256_hexdigest: {
      'loc': {
        (imagefap_image_id-1, imagefap_full_res_url-1, imagefap_file_name-1, user_id-1, folder_id-1),
        (imagefap_image_id-2, imagefap_full_res_url-2, imagefap_file_name-2, user_id-2, folder_id-2),
        ... this is a set of every occurance of the blob in the downloaded favorites ...
      }
      'tags': {tag_id-1, tag_id-2, ...}
    }
  }
  'imageidsidx': {
    # this is a reverse index for 'blobs' so we can easily search by imagefap_image_id
    imagefap_image_id: file_sha_256_hexdigest
  }

}
```
