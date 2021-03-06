# --------------------------------------------------------------------------
# Copyright (c) 2015-2017 Digital Sapphire
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the
# following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF
# ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
# TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR
# ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.
# --------------------------------------------------------------------------
from __future__ import print_function, unicode_literals

import logging
import os

from dsdev_utils.paths import remove_any
from dsdev_utils.terminal import get_correct_answer
import six

from pyupdater import settings
from pyupdater.utils import remove_dot_files, PluginManager
from pyupdater.utils.exceptions import UploaderError, UploaderPluginError

log = logging.getLogger(__name__)


class Uploader(object):
    """Uploads updates to configured servers.  SSH, SFTP, S3
    Will automatically pick the correct uploader depending on
    what is configured thorough the config object

    Sets up client with config values from obj

        Args:

            config (instance): config object
    """
    def __init__(self, config=None):
        # Specifies whether to keep a file after uploading
        self.keep = False
        if config:
            self.init(config)

    def init(self, obj):
        """Sets up client with config values from obj

        Args:

            obj (instance): config object
        """
        data_dir = os.path.join(os.getcwd(), settings.USER_DATA_FOLDER)
        self.deploy_dir = os.path.join(data_dir, 'deploy')

        # The upload plugin that'll be used to upload our files
        self.uploader = None

        # Files to be uploaded
        self.files = []

        # Extension Manager
        # ToDo: Make this a more descriptive variable name
        self.mgr = PluginManager(obj)

    def get_plugin_names(self):
        return self.mgr.get_plugin_names()

    def set_uploader(self, requested_uploader, keep=False):
        """Sets the named upload plugin.

        Args:

            requested_uploader (string): Either s3 or scp

            keep (bool): False to delete files after upload, True to keep files. Default False.

        """
        self.keep = keep
        if isinstance(requested_uploader, six.string_types) is False:
            raise UploaderError('Must pass str to set_uploader',
                                expected=True)

        self.uploader = self.mgr.get_plugin(requested_uploader, init=True)
        if self.uploader is None:
            log.debug('PLUGIN_NAMESPACE: %s', self.mgr.PLUGIN_NAMESPACE)
            raise UploaderPluginError('Requested uploader is not installed',
                                      expected=True)

        msg = 'Requested uploader: {}'.format(requested_uploader)
        log.debug(msg)

        # ToDo: Move this into it's own function.
        #            Call this new function in the upload method
        try:
            _files = os.listdir(self.deploy_dir)
        except OSError:
            _files = []

        files = []
        for f in _files:
            files.append(os.path.join(self.deploy_dir, f))

        self.files = remove_dot_files(files)
        # End ToDo

    def upload(self):
        """Uploads all files in file_list"""
        failed_uploads = []
        self.files_completed = 1
        self.file_count = len(self.files)
        log.info('Plugin: %s', self.uploader.name)
        log.info('Author: %s', self.uploader.author)
        for f in self.files:
            basename = os.path.basename(f)
            msg = '\n\nUploading: {}' .format(basename)
            msg2 = ' - File {} of {}\n'.format(self.files_completed,
                                               self.file_count)
            print(msg + msg2)
            complete = self.uploader.upload_file(f)

            if complete:
                log.debug('%s uploaded successfully', basename)
                if self.keep is False:
                    remove_any(f)
                self.files_completed += 1
            else:
                log.debug('%s failed to upload.  will retry', basename)
                failed_uploads.append(f)
        if len(failed_uploads) > 0:
            failed_uploads = self._retry_upload(failed_uploads)
        if len(failed_uploads) < 1:
            print("\nUpload Complete")
            return True
        else:
            print('The following files were not uploaded')
            for i in failed_uploads:
                log.error('%s failed to upload', os.path.basename(i))
                print(i)
            return False

    def _retry_upload(self, failed_uploads):
        # Takes list of failed downloads and tries to re upload them
        retry = failed_uploads[:]
        failed_uploads = []
        failed_count = len(retry)
        count = 1
        for f in retry:
            msg = '\n\nRetyring: {} - File {} of {}\n'.format(f, count,
                                                              failed_count)
            print(msg)
            complete = self.uploader.upload_file(f)
            if complete:
                log.debug('%s uploaded on retry', f)
                if self.keep is False:
                    remove_any(f)
                count += 1
            else:
                failed_uploads.append(f)

        return failed_uploads


# noinspection PyProtectedMember
class AbstractBaseUploaderMeta(type):

    def __call__(cls, *args, **kwargs):
        obj = type.__call__(cls, *args, **kwargs)
        # We are using this meta class to ensure plugin authors have
        # a plugin name & author name as class attributes.
        obj._check_attributes()  # noqa
        # End ignore
        return obj


@six.add_metaclass(AbstractBaseUploaderMeta)
class BaseUploader(object):
    name = None
    author = None
    """Base Uploader.  All uploaders should subclass
    this base class
    """
    def _check_attributes(self):
        if self.name is None or self.author is None:
            raise NotImplementedError

    @staticmethod
    def get_answer(question, default=None):
        return get_correct_answer(question, default=default)

    def init_config(self, config):
        """Used to initialize plugin with saved config.

        Args:

            config (dict): config dict for plugin
        """
        raise NotImplementedError('{} by {} must implemented in '
                                  'subclass.'.format(self.name, self.author))

    def set_config(self, config):
        """Used to ask user questions and return config
        for saving

        Args:

            config (dict): config dict that can be used to query
                            already set values

        """
        raise NotImplementedError('{} by {} must implemented in '
                                  'subclass.'.format(self.name, self.author))

    def upload_file(self, filename):
        """Uploads file to remote repository

        Args:
            filename (str): file to upload

        Returns:
            (bool) Meaning::

                True - Upload Successful

                False - Upload Failed
        """
        raise NotImplementedError('{} by {} must implemented in '
                                  'subclass.'.format(self.name, self.author))
