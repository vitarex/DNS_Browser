import azure.storage.blob as blob
import azure.storage.common as common
import time

a = blob.BlockBlobService("adatgyujtesteszt", None, "?sv=2018-03-28&ss=b&srt=co&sp=w&se=2019-03-08T21:34:25Z&st=2019-03-08T13:34:25Z&spr=https&sig=Y0pM6BV0sqnvXWBOyKf7FWcWCIECuKHMBiXOl7o0Tq0%3D")
a.create_blob_from_path("tesztcontainer", "tesztdbblob_" + str(time.time()), "D:\\sqlite-web\\sqlite-web\\privadome.db")
a.get_block_list("tesztcontainer", "tesztblob")