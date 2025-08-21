"""
    vdk_map.py
    Used to read the .MAP file in the data folder of the game Requiem:Desiderium Mortis.
    Kinda useless because all the data you need is already in the .VDK file that actully contains the fileCount.
"""

import struct, argparse, os, zlib, sys

FILE_NAME_SIZE = 0x60
ARCHIVE_NAME_SIZE = 0x18

def info(map_path : str):
    assert map_path.lower().endswith(".map"), "File doesn't end in .map"

    f = open(map_path, "rb")

    f.seek(0, 2) #move to end of file
    file_size = f.tell()
    f.seek(0, 0)

    while(f.tell() < file_size):
        assert(f.read(1) == b'\x00') #for some reason the strings start with a null byte
        file_name = f.read(FILE_NAME_SIZE-1).decode("ascii").replace("\x00", "")
        #print("File name: ", file_name)

        assert(f.read(1) == b'\x00')
        archive_name = f.read(ARCHIVE_NAME_SIZE-1).decode("ascii").replace("\x00", "")
        #print("Archive name: ", archive_name)

        uncompressed_size,compressed_size,unknown_always_0,offset = struct.unpack('iiii', f.read(4*4))

        #print("Uncompressed size:", uncompressed_size)
        #print("Compressed size:", compressed_size)
        #print("Offset:", offset)
        #print("")
        print(file_name, archive_name, uncompressed_size, compressed_size, offset)
    
def create(vdk_path : str):
    assert vdk_path.lower().endswith(".vdk"), "File doesn't end in .vdk"

    f_in = open(vdk_path, "rb")
    vdk_name = os.path.basename(vdk_path)
    vdk_name_without_extension = os.path.splitext(vdk_name)[0]
    f_out = open(os.path.dirname(vdk_path) + "/" + vdk_name_without_extension + ".MAP", "wb")

    _,_,file_count, dir_count, size, f_list = _get_vdk_header(f_in)

    def recursive(f, path="."):
        next_offset = 1
        while next_offset:
            file_header_offset_in_archive = f.tell()

            is_dir, name, real_size, compressed_size, doffset, next_offset = struct.unpack("<?128sIIII", f.read(145))
            name : str = name.decode("cp949").rstrip("\0")
            print(is_dir, path, name, real_size, compressed_size, doffset, next_offset)
            if is_dir:
                if name not in (".", ".."):
                    recursive(f, path + "/" + name.upper())
            else:
                file_path = path + "/" + name.upper()
                data = f.read(compressed_size)
                file_path = file_path[1:] #remove starting /
                #print(file_path, vdk_name, real_size, compressed_size, file_header_offset_in_archive)
                try:
                    write_entry(f_out, file_path, vdk_name, real_size, compressed_size, file_header_offset_in_archive)
                except Exception as e:
                    print(e)
                    sys.exit(1)
    
                #out_f = open(file_path, "wb")
                #d = zlib.decompressobj()
                #try:
                #    out_f.write(d.decompress(data))
                #    out_f.write(d.flush())
                #except zlib.error:
                #    out_f.truncate(0)
                #    out_f.seek(0)
                #    out_f.write(data)
                #out_f.close()



    recursive(f_in, "")

    f_in.close()
    f_out.close()
        

def _get_vdk_header(f_in):
    versionString, unknownInt, fileCount, dirCount, size = struct.unpack("<8sIIII", f_in.read(24))
    versionString = versionString.decode("ascii")

    fList = None
    if versionString == "VDISK1.1":
        fList = struct.unpack("<I", f_in.read(4))[0]
    elif versionString == "VDISK1.0":
        fList = 0
    else:
        assert False, "Wrong version header in vdk file"

    #print("Header:", versionString, unknownInt, fileCount, dirCount, size)

    return versionString, unknownInt, fileCount, dirCount, size, fList

def write_entry(f, file_path:str, archive_name:str, uncompressed_size:int, compressed_size:int, offset:int):
    #strings start with a null byte for some reason
    file_path = ("\x00"+file_path).encode("ascii")
    archive_name = ("\x00"+archive_name).encode("ascii")

    temp = struct.pack(
        str(FILE_NAME_SIZE)+"s"+str(ARCHIVE_NAME_SIZE)+"sIIII",
        file_path,archive_name,uncompressed_size,compressed_size,0,offset)
    
    f.write(temp)

    #print("Writen at:", f.tell())
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="vdk_to_map", description="Creates or parses Requiem .MAP files.")
    parser.add_argument("-i", "--info", type=info, metavar="FILE")
    parser.add_argument("-c", "--create", type=create, metavar="FILE")
    args = parser.parse_args()
    #extract(args.filename)