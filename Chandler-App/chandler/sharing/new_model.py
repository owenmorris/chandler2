import chandler.sharing.eim as eim

keywordID = eim.TextType("cid:keyword_type@osaf.us", size=512)

class KeywordRecord(eim.Record):
    URI = "http://osafoundation.org/eim/keyword/0"

    # a keywordID should look like @keyword:key_value
    keywordID = eim.key(keywordID)

    # mimicking legacy_model.CollectionRecord for convenience
    colorRed = eim.key(eim.IntType)
    colorGreen = eim.key(eim.IntType)
    colorBlue = eim.key(eim.IntType)
    colorAlpha = eim.key(eim.IntType)
    checked = eim.field(eim.IntType, default=0)
