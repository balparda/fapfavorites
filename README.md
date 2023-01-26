# Imagefap Favorites

Python code that downloads an entire Imagefap favorites image collection,
de-dups, and helps organize them.

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

For now, just the basic download if you know the user ID, folder ID, and
give it an output directory.

```
./imagefap-favorites.py --id 1234 --folder 5678 --output "~/somedir/"
```

Many more features to come. Just laying the groundwork for now.
