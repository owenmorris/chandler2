import os
import sys
import wx
import cStringIO
import pkg_resources

imageCache = {}

__all__ = ('get_raw_image', 'get_image')

def get_raw_image(name, copy=True):
    """
    Return None if image isn't found, otherwise return the raw image.
    Also look first for platform specific images.
    """
    global imageCache
    entry = imageCache.get(name)
    if entry is not None:
        image = entry[0]
        if image is not None and copy:
            image = image.Copy()
        return image

    root, extension = os.path.splitext(name)
    
    # This hardcodes the resources/images path that's specified in
    # resources.ini inside the Chandler_App.egg-info.
    dist = pkg_resources.get_distribution("Chandler_App")
    
    def readData(path):
        try:
            return dist.get_metadata(path)
        except IOError:
            return None
        
    data = readData("resources/images/%s-%s%s" % (root, sys.platform, extension))
    if data is None:
        data = readData("resources/images/%s" % name)
    
    if data is None:
        imageCache[name] = [None]
        return None

    image = wx.ImageFromStream(cStringIO.StringIO(data))
    imageCache[name] = [image]
    if copy:
        image = image.Copy()
    return image

def get_image(name):
    """
    Return None if image isn't found, otherwise loads a bitmap.
    Looks first for platform specific bitmaps.
    """
    rawImage = get_raw_image(name, copy=False)
    if rawImage is not None:
        return wx.BitmapFromImage(rawImage)
    else:
        return None
