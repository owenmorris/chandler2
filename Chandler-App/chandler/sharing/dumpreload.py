#   Copyright (c) 2003-2008 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


"""Dump and Reload module"""

from __future__ import with_statement

import logging, cPickle, sys, os, platform, tempfile
from gzip import GzipFile
from chandler.sharing import eim, translator
from pkg_resources import iter_entry_points

logger = logging.getLogger(__name__)

class UnknownRecord(object):
    """Class representing an unknown record type"""
    def __init__(self, *args):
        self.data = args


class PickleSerializer(object):
    """ Serializes to a byte-length string, followed by newline, followed by
        a pickle string of the specified length """

    @classmethod
    def dumps(cls, ob):
        from cStringIO import StringIO
        s = StringIO()
        cls.dumper(s)(ob)
        return s.getvalue()

    @classmethod
    def loads(cls, s):
        from cStringIO import StringIO
        return cls.loader(StringIO(s))()

    @classmethod
    def dumper(cls, output):
        pickler = cPickle.Pickler(output, 2)
        pickler.persistent_id = cls.persistent_id
        return pickler.dump

    @classmethod
    def loader(cls, input):
        unpickler = cPickle.Unpickler(input)
        unpickler.persistent_load = cls.persistent_load
        unpickler.find_global = cls.find_global
        return unpickler.load

    @staticmethod
    def find_global(module, name):
        """Work around Symbol namespace differences when importing."""
        if module == 'osaf.sharing.eim':
            module = 'chandler.sharing.eim'
        if module not in sys.modules:
            __import__(module)
        return getattr(sys.modules[module], name)

    @staticmethod
    def persistent_id(ob):
        if isinstance(ob, eim.RecordClass):
            # save record classes by URI *and* module
            return ob.URI, ob.__module__

    @staticmethod
    def persistent_load((uri, module)):
        try:
            return eim.uri_registry[uri]
        except KeyError:
            pass
        # It wasn't in the registry by URI, see if we can import it
        if module not in sys.modules:
            try:
                __import__(module)
            except ImportError:
                pass
        try:
            # Maybe it's in the registry now...
            return eim.uri_registry[uri]
        except KeyError:
            # Create a dummy record type for the object
            # XXX this really should try some sort of persistent registry
            #     before falling back to a fake record type
            #
            rtype = type("Unknown", (UnknownRecord,), dict(URI=uri))
            eim.uri_registry[uri] = rtype
            return rtype

def dump(stream, uuids, serializer=PickleSerializer, obfuscate=False, gzip=False):

    translator_class = getTranslator()

    trans = translator_class()
    trans.obfuscation = obfuscate

    if not uuids:
        uuids = ()
    aliases = uuids

    # Sort on alias so masters are dumped before occurrences
    aliases.sort()

    trans.startExport()

    if gzip:
        stream = GzipFile(fileobj=stream)

    dump = serializer.dumper(stream)

    for alias in aliases:
        item = trans.getItemForAlias(alias)
        for record in trans.exportItem(item):
            dump(record)

    for record in trans.finishExport():
        dump(record)

    dump(None)
    if gzip:
        stream.close()

    del dump

def overwrite_rename(from_path, to_path):
    """Move file in from_path to to_path, deleting to_path if it already exists.

    On non-windows platforms, this is equivalent to
    os.rename(from_path, to_path), but on Windows this will fail if
    to_path already exists, so delete to_path first.

    """
    if platform.system() == 'Windows':
        try:
            os.remove(to_path)
        except OSError, err:
            if err.errno != 2:
                logger.exception("Unable to remove %s", path)
                raise

    os.rename(from_path, to_path)


def dump_to_path(path, uuids=None, serializer=PickleSerializer, obfuscate=False, gzip=False):
    """
    Dumps EIM records to a file, file permissions 0600.
    """

    # Paths here:
    #
    #  temppath - a temporary path with a .temp extension. This helps avoid
    #             the situation where we try to reload from a half-written
    #             .chex file
    #
    #  completedpath - a temporary path with a .chex extension (actually, with
    #       the same extension as the passed-in path). If there are problems
    #       writing to the requested path, this at least leaves a complete
    #       .chex file on disk as a backup.
    #
    dir, filename = os.path.split(path)
    basename, ext = os.path.splitext(filename)

    fd, temppath = tempfile.mkstemp(ext + ".temp", basename, dir)
    completedpath = None

    # First, make the file read-only by the user.
    os.chmod(temppath, 0600)

    try:
        with os.fdopen(fd, 'wb') as output:
            dump(output, uuids, serializer, obfuscate, gzip)

        # Next, remove the .temp from the filename. This means that
        # we have a complete, recoverable .chex file on disk (yay).
        completedpath = os.path.splitext(temppath)[0]
        os.rename(temppath, completedpath)
        temppath = None
        overwrite_rename(completedpath, path)
        completedpath = None

    except:
        logger.exception("Error during export")
        if temppath is not None:
            try:
                os.remove(temppath)
            except OSError:
                logger.exception("Unable to remove %s -- ignoring", temppath)

        raise

def reload(filename_or_stream, serializer=PickleSerializer, gzip=False):
    """ Loads EIM records from a file and applies them """


    if isinstance(filename_or_stream, basestring):
        input = open(filename_or_stream, "rb")
    else:
        input = filename_or_stream

    original_input = input
    if gzip:
        input = GzipFile(fileobj=input)


    translator_class = getTranslator()

    trans = translator_class()
    trans.startImport()

    try:
        load = serializer.loader(input)
        i = 0
        alias_in_progress = None
        records = []
        while True:
            record = load()
            if not record:
                trans.importRecords(eim.Diff(records))
                break
            if not getattr(record, 'uuid', None):
                if records:
                    trans.importRecords(eim.Diff(records))
                records = []
                alias_in_progress = None
                trans.importRecord(record)
            elif record.uuid == alias_in_progress:
                records.append(record)
            elif not records:
                alias_in_progress = record.uuid
                records.append(record)
            else:
                trans.importRecords(eim.Diff(records))
                records = [record]
                alias_in_progress = record.uuid
            i += 1

        logger.info("Imported %d records", i)

        del load
    finally:
        input.close()
        original_input.close()

    trans.finishImport()


def convertToTextFile(fromPath, toPath, serializer=PickleSerializer):

    input = open(fromPath, "rb")
    output = open(toPath, "wb")
    try:
        load = serializer.loader(input)
        i = 0
        while True:
            record = load()
            if not record:
                break
            output.write(str(record))
            output.write("\n\n")
            i += 1

        del load
    finally:
        input.close()
        output.close()


TRANSLATOR_CLASS = None

def getTranslator():
    global TRANSLATOR_CLASS

    if TRANSLATOR_CLASS is not None:
        return TRANSLATOR_CLASS

    mixins = [ep.load() for ep in iter_entry_points('chandler.chex_mixins')]
    if not mixins:
        TRANSLATOR_CLASS = translator.DumpTranslator
    else:
        mixins.insert(0, translator.DumpTranslator)
        TRANSLATOR_CLASS = type("Translator", tuple(mixins),
            {
                'version'     : 1,
                'URI'         : ' '.join(m.URI for m in mixins),
                'description' : u'Mixed-in translator'
            }
        )
    return TRANSLATOR_CLASS
