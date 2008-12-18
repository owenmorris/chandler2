#   Copyright (c) 2003-2007 Open Source Applications Foundation
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



from chandler.sharing import eim, errors
from simplegeneric import generic
import PyICU, vobject, datetime, dateutil, itertools
import base64, decimal, re
from dateutil.parser import parse as dateutilparser
from xml.etree.cElementTree import (
    Element, SubElement, tostring, fromstring
)



__all__ = [
    'EIMMLSerializer',
    'EIMMLSerializerLite',
]


# below 0x20, only 0x09 (tab), 0x0a (nl), and 0x0d (cr) are allowed
xmlUnfriendly = re.compile("[\x00-\x08|\x0b|\x0c|\x0e-\x1f]")




@generic
def serializeValue(typeinfo, value):
    """Serialize a value based on typeinfo"""
    raise NotImplementedError("Unrecognized type:", typeinfo)

@serializeValue.when_type(eim.BytesType)
def serialize_bytes(typeinfo, value):
    if value is None:
        return None, "bytes"
    return base64.b64encode(value), "bytes"

@serializeValue.when_type(eim.IntType)
def serialize_int(typeinfo, value):
    if value is None:
        return None, "integer"
    return str(value), "integer"

@serializeValue.when_type(eim.TextType)
def serialize_text(typeinfo, value):
    if value is None:
        return None, "text"
    return value, "text"

@serializeValue.when_type(eim.BlobType)
def serialize_blob(typeinfo, value):
    if value is None:
        return None, "blob"
    return base64.b64encode(value), "blob"

@serializeValue.when_type(eim.ClobType)
def serialize_clob(typeinfo, value):
    if value is None:
        return None, "clob"
    return value, "clob"

@serializeValue.when_type(eim.DateType)
def serialize_date(typeinfo, value):
    if value is None:
        return None, "datetime"
    return value.isoformat(), "datetime"

@serializeValue.when_type(eim.DecimalType)
def serialize_decimal(typeinfo, value):
    if value is None:
        return None, "decimal"
    return str(value), "decimal"




@generic
def deserializeValue(typeinfo, text):
    """Deserialize text based on typeinfo"""
    raise NotImplementedError("Unrecognized type:", typeinfo)

@deserializeValue.when_type(eim.BytesType)
def deserialize_bytes(typeinfo, text):
    return base64.b64decode(text)

@deserializeValue.when_type(eim.IntType)
def deserialize_int(typeinfo, text):
    return int(text)

@deserializeValue.when_type(eim.TextType)
def deserialize_text(typeinfo, text):
    return text

@deserializeValue.when_type(eim.BlobType)
def deserialize_blob(typeinfo, text):
    return base64.b64decode(text)

@deserializeValue.when_type(eim.ClobType)
def deserialize_clob(typeinfo, text):
    return text

@deserializeValue.when_type(eim.DecimalType)
def deserialize_decimal(typeinfo, text):
    return decimal.Decimal(text)

@deserializeValue.when_type(eim.DateType)
def deserialize_date(typeinfo, text):
    return convertToICUtzinfo(dateutilparser(text))





eimURI = "http://osafoundation.org/eim/0"
keyURI = "{%s}key" % eimURI
typeURI = "{%s}type" % eimURI
deletedURI = "{%s}deleted" % eimURI

class EIMMLSerializer(object):

    @classmethod
    def serialize(cls, recordSets, rootName="collection", **extra):
        """ Convert a list of record sets to XML text """


        rootElement = Element("{%s}%s" % (eimURI, rootName), **extra)

        # Sorting by uuid here to guarantee we send masters before
        # modifications (for the benefit of Cosmo).  If we ever change
        # the recurrenceID uuid scheme, this will have to be updated.
        uuids = recordSets.keys()
        uuids.sort()
        for uuid in uuids:
            recordSet = recordSets[uuid]

            if recordSet is not None:

                recordSetElement = SubElement(rootElement,
                    "{%s}recordset" % eimURI, uuid=uuid)

                for record in eim.sort_records(recordSet.inclusions):
                    recordElement = SubElement(recordSetElement,
                        "{%s}record" % (record.URI))

                    for field in record.__fields__:
                        value = record[field.offset]

                        if value is eim.NoChange:
                            continue

                        else:

                            attrs = { }

                            if value is eim.Inherit:
                                serialized, typeName = serializeValue(
                                        field.typeinfo, None)
                                attrs["missing"] = "true"

                            else:
                                serialized, typeName = serializeValue(
                                        field.typeinfo, value)
                                if value == "":
                                    attrs["empty"] = "true"

                            if typeName is not None:
                                attrs[typeURI] = typeName

                            if isinstance(field, eim.key):
                                attrs[keyURI] = "true"

                            fieldElement = SubElement(recordElement,
                                "{%s}%s" % (record.URI, field.name),
                                **attrs)

                            fieldElement.text = serialized

                for record in list(recordSet.exclusions):
                    attrs = { deletedURI : "true"}
                    recordElement = SubElement(recordSetElement,
                        "{%s}record" % (record.URI), **attrs)

                    for field in record.__fields__:
                        if isinstance(field, eim.key):
                            value = record[field.offset]
                            serialized, typeName = serializeValue(
                                field.typeinfo, record[field.offset])
                            attrs = { keyURI : 'true' }
                            if typeName is not None:
                                attrs[typeURI] = typeName
                            if value == "":
                                attrs["empty"] = "true"
                            fieldElement = SubElement(recordElement,
                                "{%s}%s" % (record.URI, field.name),
                                **attrs)
                            fieldElement.text = serialized

            else: # item deletion indicated

                attrs = { deletedURI : "true"}
                recordSetElement = SubElement(rootElement,
                    "{%s}recordset" % eimURI, uuid=uuid, **attrs)


        xmlString = xmlUnfriendly.sub("", tostring(rootElement))
        return "<?xml version='1.0' encoding='UTF-8'?>%s" % xmlString

    @classmethod
    def deserialize(cls, text, **kwargs):
        """ Parse XML text into a list of record sets """

        try:
            rootElement = fromstring(text) # xml parser
        except Exception, e:
            errors.annotate(e, "Couldn't parse XML",
                details=text[:5000].encode("string_escape"))
            raise

        recordSets = {}
        for recordSetElement in rootElement:
            uuid = recordSetElement.get("uuid")

            deleted = recordSetElement.get(deletedURI)
            if deleted and deleted.lower() == "true":
                recordSet = None

            else:
                inclusions = []
                exclusions = []

                for recordElement in recordSetElement:
                    ns, name = recordElement.tag[1:].split("}")

                    recordClass = eim.lookupSchemaURI(ns)
                    if recordClass is None:
                        continue    # XXX handle error?  logging?

                    values = []
                    for field in recordClass.__fields__:
                        for fieldElement in recordElement:
                            ns, name = fieldElement.tag[1:].split("}")
                            if field.name == name:
                                empty = fieldElement.get("empty")
                                missing = fieldElement.get("missing")
                                if empty and empty.lower() == "true":
                                    value = ""
                                elif missing and missing.lower() == "true":
                                    value = eim.Inherit
                                else:
                                    if fieldElement.text is None:
                                        value = None
                                    else:
                                        value = deserializeValue(
                                            field.typeinfo,
                                            fieldElement.text)
                                break
                        else:
                            value = eim.NoChange

                        values.append(value)

                    record = recordClass(*values)

                    deleted = recordElement.get(deletedURI)
                    if deleted and deleted.lower() == "true":
                        if record is eim.NoChange:
                            record = recordClass(*
                                [(eim.Inherit if v is eim.NoChange else v)
                                for v in values]
                            )
                        exclusions.append(record)
                    else:
                        inclusions.append(record)

                recordSet = eim.Diff(inclusions, exclusions)

            recordSets[uuid] = recordSet

        return recordSets, dict(rootElement.items())



def convertToICUtzinfo(dt):
    """
    Return a C{datetime} whose C{tzinfo} field
    (if any) is an instance of the ICUtzinfo class.

    @param dt: The C{datetime} whose C{tzinfo} field we want
               to convert to an ICUtzinfo instance.
    @type dt: C{datetime}
    """
    icuTzinfo = olsonizeTzinfo(dt.tzinfo, dt)

    if not hasattr(dt, 'hour'):
        dt = forceToDateTime(dt, icuTzinfo)
    else:
        dt = dt.replace(tzinfo=icuTzinfo)

    return dt

tzid_mapping = {}
dateutil_utc = dateutil.tz.tzutc()
# PyICU's tzids match whatever's in zoneinfo, which is essentially the Olson
# timezone database
olson_tzids = tuple(PyICU.TimeZone.createEnumeration())

def getICUInstance(name):
    """Return an ICUInstance, or None for false positive GMT results."""
    result = None
    if name is not None:
        result = PyICU.ICUtzinfo.getInstance(name)
        if result is not None and \
            result.tzid == 'GMT' and \
            name != 'GMT':
            result = None

    return result


def olsonizeTzinfo(oldTzinfo, dt=None):
    """Turn oldTzinfo into an ICUtzinfo whose tzid matches something in the Olson db.
    """
    if (isinstance(oldTzinfo, PyICU.FloatingTZ) or
        (isinstance(oldTzinfo, PyICU.ICUtzinfo) and oldTzinfo.tzid in olson_tzids)):
        # if tzid isn't in olson_tzids, ICU is using a bogus timezone, bug 11784 
        return oldTzinfo
    elif oldTzinfo is None:
        icuTzinfo = None # Will patch to floating at the end
    else:
        year_start = 2007 if dt is None else dt.year
        year_end = year_start + 1

        # First, for dateutil.tz._tzicalvtz, we check
        # _tzid, since that's the displayable timezone
        # we want to use. This is kind of cheesy, but
        # works for now. This means that we're preferring
        # a tz like 'America/Chicago' over 'CST' or 'CDT'.
        tzical_tzid = getattr(oldTzinfo, '_tzid', None)
        icuTzinfo = getICUInstance(tzical_tzid)

        if tzical_tzid is not None:
            if tzical_tzid in tzid_mapping:
                # we've already calculated a tzinfo for this tzid
                icuTzinfo = tzid_mapping[tzical_tzid]

        if icuTzinfo is None:
            # special case UTC, because dateutil.tz.tzutc() doesn't have a TZID
            # and a VTIMEZONE isn't used for UTC
            if vobject.icalendar.tzinfo_eq(dateutil_utc, oldTzinfo):
                icuTzinfo = PyICU.ICUtzinfo.UTC

        # iterate over all PyICU timezones, return the first one whose
        # offsets and DST transitions match oldTzinfo.  This is painfully
        # inefficient, but we should do it only once per unrecognized timezone,
        # so optimization seems premature.
        backup = None
        if icuTzinfo is None:
            well_known = [] # XXX replace view-based well-known timezones with something else
            # canonicalTimeZone doesn't help us here, because our matching
            # criteria aren't as strict as PyICU's, so iterate over well known
            # timezones first
            for tzid in itertools.chain(well_known, olson_tzids):
                test_tzinfo = getICUInstance(tzid)
                # only test for the DST transitions for the year of the event
                # being converted.  This could be very wrong, but sadly it's
                # legal (and common practice) to serialize VTIMEZONEs with only
                # one year's DST transitions in it.  Some clients (notably iCal)
                # won't even bother to get that year's offset transitions right,
                # but in that case, we really can't pin down a timezone
                # definitively anyway (fortunately iCal uses standard zoneinfo
                # tzid strings, so getICUInstance above should just work)
                #
                # Also, don't choose timezones in Antarctica, when we're guessing
                # we might as well choose a location with human population > 100.
                if (not tzid.startswith('Antarctica') and
                    vobject.icalendar.tzinfo_eq(test_tzinfo, oldTzinfo,
                                               year_start, year_end)):
                    icuTzinfo = test_tzinfo
                    if tzical_tzid is not None:
                        tzid_mapping[tzical_tzid] = icuTzinfo
                    break
                # sadly, with the advent of the new US timezones, Exchange has
                # chosen to serialize US timezone DST transitions as if they
                # began in 1601, so we can't rely on dt.year.  So also try
                # 2007-2008, but treat any matches as a backup, they're
                # less reliable, since the VTIMEZONE may not define DST
                # transitions for 2007-2008.  Keep the first match, since we
                # process well known timezones first, and there's no way to
                # distinguish between, say, America/Detroit and America/New_York
                # in the 21st century.
                if backup is None:
                    if vobject.icalendar.tzinfo_eq(test_tzinfo, oldTzinfo,
                                                   2007, 2008):
                        backup = test_tzinfo
        if icuTzinfo is None and backup is not None:
            icuTzinfo = backup
            if tzical_tzid is not None:
                tzid_mapping[tzical_tzid] = icuTzinfo
    # if we have an unknown timezone, we'll return floating
    return PyICU.ICUtzinfo.floating if icuTzinfo is None else icuTzinfo

def forceToDateTime(dt, tzinfo=None):
    """
    If dt is a datetime, return dt, if a date, add time(0) and return.

    @param dt: The input.
    @type dt: C{datetime} or C{date}

    @return: A C{datetime}
    """
    if tzinfo is None:
        tzinfo = PyICU.ICUtzinfo.floating
    if type(dt) == datetime.datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tzinfo)
        else:
            return dt
    elif type(dt) == datetime.date:
        return datetime.datetime.combine(dt, datetime.time(0, tzinfo=tzinfo))

