
.. image:: https://raw.githubusercontent.com/Nekmo/tgupi/master/logo.png
    :width: 100%

|

.. image:: https://raw.githubusercontent.com/Nekmo/tgupi/pip-rating-badge/pip-rating-badge.svg
  :target: https://github.com/Nekmo/tgupi/actions/workflows/pip-rating.yml
  :alt: pip-rating badge

.. image:: https://img.shields.io/github/actions/workflow/status/Nekmo/tgupi/test.yml?style=flat-square&maxAge=2592000&branch=master
  :target: https://github.com/Nekmo/tgupi/actions?query=workflow%3ATests
  :alt: Latest Tests CI build status

.. image:: https://img.shields.io/pypi/v/tgupi.svg?style=flat-square
  :target: https://pypi.org/project/tgupi/
  :alt: Latest PyPI version

.. image:: https://img.shields.io/pypi/pyversions/tgupi.svg?style=flat-square
  :target: https://pypi.org/project/tgupi/
  :alt: Python versions

.. image:: https://img.shields.io/codeclimate/maintainability/Nekmo/tgupi.svg?style=flat-square
  :target: https://codeclimate.com/github/Nekmo/tgupi
  :alt: Code Climate

.. image:: https://img.shields.io/codecov/c/github/Nekmo/tgupi/master.svg?style=flat-square
  :target: https://codecov.io/github/Nekmo/tgupi
  :alt: Test coverage

.. image:: https://img.shields.io/github/stars/Nekmo/tgupi?style=flat-square
     :target: https://github.com/Nekmo/tgupi
     :alt: Github stars


###############
tgupi
###############
Telegram-upload uses your **personal Telegram account** to **upload** and **download** files up to **4 GiB** (2 GiB for
free users). Turn Telegram into your personal ☁ cloud!

To **install 🔧 tgupi**, run this command in your terminal:

.. code-block:: console

    $ sudo pip3 install -U tgupi

This is the preferred method to install tgupi, as it will always install the most recent stable release.
🐍 **Python 3.7-3.11** are tested and supported. There are other installation ways available like `Docker <#-docker>`_.
More info in the `📕 documentation <https://docs.nekmo.org/tgupi/installation.html>`_

.. image:: https://raw.githubusercontent.com/Nekmo/tgupi/master/tgupi-demo.gif
  :target: https://asciinema.org/a/592098
  :width: 100%

❓ Usage
========
To use this program you need an Telegram account and your **App api_id & api_hash** (get it in
`my.telegram.org <https://my.telegram.org/>`_). The first time you use tgupi it requests your
📱 **telephone**, **api_id** and **api_hash**. Bot tokens can not be used with this program (bot uploads are limited to
50MB).

To **send ⬆️ files** (by default it is uploaded to saved messages):

.. code-block:: console

    $ tgupi file1.mp4 file2.mkv

You can **download ⤵️ the files** again from your saved messages (by default) or from a channel. All files will be
downloaded until the last text message.

.. code-block:: console

    $ telegram-download

`Read the documentation <https://docs.nekmo.org/tgupi/usage.html#telegram-download>`_ for more info about the
options availables.

Interactive mode
----------------
The **interactive option** (``--interactive``) allows you to choose the dialog and the files to download or upload with
a **terminal 🪄 wizard**. It even **supports mouse**!

.. code-block:: console

    $ tgupi --interactive    # Interactive upload
    $ telegram-download --interactive  # Interactive download

`More info in the documentation <https://docs.nekmo.org/tgupi/usage.html#interactive-mode>`_

Set group or chat
-----------------
By default when using tgupi without specifying the recipient or sender, tgupi will use your personal
chat. However you can define the 👨 destination. For file upload the argument is ``--to <entity>``. For example:

.. code-block::

    $ tgupi --to telegram.me/joinchat/AAAAAEkk2WdoDrB4-Q8-gg video.mkv

You can download files from a specific chat using the --from <entity> parameter. For example:

.. code-block::

    $ telegram-download --from username

You can see all `the possible values for the entity in the documentation <https://docs.nekmo.org/tgupi/usage.html#set-recipient-or-sender>`_.

Split & join files
------------------
If you try to upload a file that **exceeds the maximum supported** by Telegram by default, an error will occur. But you
can enable ✂ **split mode** to upload multiple files:

.. code-block:: console

    $ tgupi --large-files split large-video.mkv

Files split using split can be rejoined on download using:

.. code-block:: console

    $ telegram-download --split-files join

Find more help in `the tgupi documentation <https://docs.nekmo.org/tgupi/usage.html#split-files>`_.

Delete on success
-----------------
The ``--delete-on-success`` option allows you to ❌ **delete the Telegram message** after downloading the file. This is
useful to send files to download to your saved messages and avoid downloading them again. You can use this option to
download files on your computer away from home.

Configuration
-------------
Credentials are saved in ``~/.config/tgupi.json`` and ``~/.config/tgupi.session``. You must make
sure that these files are secured. You can copy these 📁 files to authenticate ``tgupi`` on more machines, but
it is advisable to create a session file for each machine.

More options
------------
Telegram-upload has more options available, like customizing the files thumbnail, set a caption message (including
variables) or configuring a proxy.
`Read the documentation <https://docs.nekmo.org/tgupi/usage.html#telegram-download>`_ for more info.

💡 Features
===========

* **Upload** and **download** multiples files  (up to 4 GiB per file for premium users).
* **Interactive** mode.
* Add video **thumbs**.
* **Split** and **join** large files.
* **Delete** local or remote file on success.
* Use **variables** in the **caption** message.
* ... And **more**.

🐋 Docker
=========
Run tgupi without installing it on your system using Docker. Instead of ``tgupi``
and ``telegram-download`` you should use ``upload`` and ``download``. Usage::


    $ docker run -v <files_dir>:/files/
                 -v <config_dir>:/config
                 -it nekmo/tgupi:master
                 <command> <args>

* ``<files_dir>``: upload or download directory.
* ``<config_dir>``: Directory that will be created to store the tgupi configuration.
  It is created automatically.
* ``<command>``: ``upload`` and ``download``.
* ``<args>``: ``tgupi`` and ``telegram-download`` arguments.

For example::

    $ docker run -v /media/data/:/files/
                 -v $PWD/config:/config
                 -it nekmo/tgupi:master
                 upload file_to_upload.txt

❤️ Thanks
=========
This project developed by `Nekmo <https://github.com/Nekmo>`_ & `collaborators <https://github.com/Nekmo/tgupi/graphs/contributors>`_ would not be possible without
`Telethon <https://github.com/LonamiWebs/Telethon>`_, the library used as a Telegram client.

Telegram-upload is licensed under the `MIT license <https://github.com/Nekmo/tgupi/blob/master/LICENSE>`_.
