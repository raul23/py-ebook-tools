"""Removes extras (e.g. annotations and bookmarks) from ebook files.

It can remove annotations (incl. highlights, comments, notes, arrows),
bookmarks and attachments from ebook files based on the following methods:

- `cpdf`_ to remove bookmarks and attachments
- `pdftk`_ to remove annotations

For the moment, only PDF files are supported.

References
----------

.. URLs
.. _cpdf: https://community.coherentpdf.com/
.. _pdftk: https://stackoverflow.com/a/49614525/14664104
"""
from pyebooktools.utils.logutils import init_log

logger = init_log(__name__, __file__)


def remove(input_data, **kwargs):
    logger.warning('Not implemented yet!')
