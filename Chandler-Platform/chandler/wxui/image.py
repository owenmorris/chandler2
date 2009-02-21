import os
import sys
import wx
import cStringIO
import pkg_resources

imageCache = {}

__all__ = ('get_raw_image', 'get_image')

def get_raw_image(name, dist_name, copy=True):
    """
    Search for the image named 'name' inside the distribution
    named 'dist_name', and return a wx.Image if one can be
    found and created. Otherwise, return C{None}. Note that
    this function also searches for platform-specific variants
    by first checking for image resources called name-platform.

    @param name: The name of the image to search for.
    @type name: C{basestring}

    @param dist_name: The name of the distribution to search
                      for the given image.
    @type dist_name: C{basestring}

    @keyword copy: Whether or not to Copy the returned image
                   (i.e. C{True} if you want to tweak it
                   in-memory).
    @type copy: C{bool}

    @rtype: C{wx.Image} (or ${None).
    """

    global imageCache
    entry = imageCache.get((name, dist_name))
    if entry is not None:
        image = entry[0]
        if image is not None and copy:
            image = image.Copy()
        return image

    root, extension = os.path.splitext(name)
    
    dist = pkg_resources.get_distribution(dist_name)
    
    def readData(path):
        try:
            return dist.get_metadata(path)
        except IOError:
            return None
        
    data = readData("resources/images/%s-%s%s" % (root, sys.platform, extension))
    if data is None:
        data = readData("resources/images/%s" % name)
    
    if data is None:
        imageCache[(name, dist_name)] = [None]
        return None

    image = wx.ImageFromStream(cStringIO.StringIO(data))
    imageCache[(name, dist_name)] = [image]
    if copy:
        image = image.Copy()
    return image

def get_image(name):
    """
    Return None if image isn't found, otherwise loads a bitmap.
    Looks first for platform specific bitmaps.
    """
    rawImage = get_raw_image(name, dist_name, copy=False)
    if rawImage is not None:
        return wx.BitmapFromImage(rawImage)
    else:
        return None
