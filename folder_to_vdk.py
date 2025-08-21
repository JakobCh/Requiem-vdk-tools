
import zlib, os, sys, argparse, struct


HEADER_SIZE = 24
G_file_count = 0
G_dir_count = 0

# entry struct
# byte isDir
# char[128] name
# int uncompressed_size; 0 if dir
# int compressed_size; 0 if dir
# int directory_offset; 0 if file, if dir: if name is the dir name or "." point to ".". If name is ".." point to the "." one dir up.
# int next_offset; offset to the next file/dir that's in the same dir as this entry

class Entry:
    def __init__(self, isDir, name, u_size, c_size, data, parent):
        self.isDir:bool = isDir
        self.name:str = name #size 128
        self.u_size:int = u_size
        self.c_size:int = c_size
        self.directory_offset:int = 0 #wont be known at creation
        self.next_offset:int = 0
        self.data:bytes = data #[c_size]

        self._parent:Entry = parent
        self._children = []
        if self._parent:
            self._parent._children.append(self)
        self._my_offset = 0

    def get_size(self):
        return 145 + self.c_size
    
    def get_real_path(self):
        if self._parent:
            return os.path.join(self._parent.get_real_path(), self.name)
        else:
            return ""
        
    def get_fake_path(self):
        if self._parent:
            return self._parent.get_fake_path() + "/" + self.name
        else:
            return ""
        
    def get_child_by_name(self, name):
        for c in self._children:
            if c.name == name:
                return c
        return None
    
    def do_dir(self, realpath, fakepath):
        
        new_real_path = os.path.join(realpath, self.name)
        new_fake_path = fakepath + "/" + self.name

        e = Entry(True, ".", 0, 0, b"", self)
        #e.print()
        e = Entry(True, "..", 0, 0, b"", self)
        #e.print()


        for s in os.listdir(new_real_path):
            my_real_path = os.path.join(new_real_path, s)
            isDir = os.path.isdir(my_real_path)
            if isDir:
                e = Entry(True, s, 0, 0, b"", self)
                #e.print()
                e.do_dir(new_real_path, new_fake_path)
            else:
                e = Entry(False, s, 0, 0, b"", self)
                #e.print()

        return

    def write(self, f):
        f.write(struct.pack("<?128sIIII",
                            self.isDir,
                            self.name.encode("ascii"),
                            self.u_size,
                            self.c_size,
                            self.directory_offset,
                            self.next_offset
                            ))
        f.write(self.data)
        for c in self._children:
            c.write(f)

    def print(self):
        if self._parent:
            fake_dir = self._parent.get_fake_path()
        else:
            fake_dir = ""
        print(self.isDir, fake_dir, self.name, self.u_size, self.c_size, self.directory_offset, self.next_offset)
        return


def build_tree(folder_path:str):

    archive_path = ""
    root_entry = Entry(True, ".", 0, 0, b"", None)
    #root_entry.print()

    for s in os.listdir(folder_path):
        my_real_path = os.path.join(folder_path, s)
        isDir = os.path.isdir(my_real_path)
        if isDir:
            e = Entry(True, s, 0, 0, b"", root_entry)
            #e.print()
            e.do_dir(folder_path, archive_path)
        else:
            e = Entry(False, s, 0, 0, b"", root_entry)
            #e.print()

    return root_entry

def load_files(folder_path:str, root_entry:Entry, offset:int):
    root_entry._my_offset = offset
    
    if root_entry.isDir:
        offset += root_entry.get_size()
        for child in root_entry._children:
            offset = load_files(folder_path, child, offset)
    else:
        path = os.path.join(folder_path, root_entry.get_real_path())
        #print(path)
        f = open(path, "rb")
        f.seek(0,2)
        root_entry.u_size = f.tell()
        f.seek(0,0)
        root_entry.data = zlib.compress(f.read(), 1)
        root_entry.c_size = len(root_entry.data)
        #print(size,c_size)
        #root_entry.print()
        f.close()
        offset += root_entry.get_size()
    

    return offset

def set_offsets(entry:Entry, current_offset:int, index:int):

    if not entry._parent: #root entry
        entry.directory_offset = current_offset
        entry.next_offset = current_offset + entry.get_size()
        current_offset += entry.get_size()
        for i in range(len(entry._children)):
            current_offset = set_offsets(entry._children[i], current_offset, i)
        
    elif entry.isDir:
        if entry.name == ".":
            entry.directory_offset = current_offset
            entry.next_offset = current_offset + entry.get_size()
            current_offset += entry.get_size()
        elif entry.name == "..":
            p = entry._parent._parent
            if p.name == ".": #root node
                entry.directory_offset = p.directory_offset
            else:
                entry.directory_offset = entry._parent._parent.get_child_by_name(".").directory_offset
            
            if len(entry._parent._children) > index+1:
                entry.next_offset = entry._parent._children[index+1]._my_offset
                #print("---", entry._parent._children[index+1].name)
            else:
                entry.next_offset = 0


            current_offset += entry.get_size()
        else: #normal define dir
            entry.directory_offset = entry.get_child_by_name(".")._my_offset
            if len(entry._parent._children) > index+1:
                entry.next_offset = entry._parent._children[index+1]._my_offset
                #print("---", entry._parent._children[index+1].name)
            else:
                entry.next_offset = 0


            current_offset += entry.get_size()
            for i in range(len(entry._children)):
                current_offset = set_offsets(entry._children[i], current_offset, i)
            
            global G_dir_count
            G_dir_count += 1
    else:
        #files
        entry.directory_offset = 0 #0 for files
        if len(entry._parent._children) > index+1:
            entry.next_offset = entry._parent._children[index+1]._my_offset
        else:
            entry.next_offset = 0
        current_offset += entry.get_size()
        
        global G_file_count
        G_file_count += 1

    return current_offset

def save_tree(filepath:str, root_entry:Entry, filesize:int):
    f = open(filepath, "wb")
    #print(filesize,HEADER_SIZE)
    f.write(struct.pack("<8sIIII",
                "VDISK1.0".encode("ascii"),
                0,
                G_file_count,
                G_dir_count,
                filesize-145, #I honestly thought this was -HEADER_SIZE??
                ))
    
    root_entry.write(f)
    f.close()

    

def print_everything(entry:Entry):
    entry.print()
    for c in entry._children:
        print_everything(c)

def run(folder_path:str):
    #print("Building tree")
    root_entry = build_tree(folder_path)
    #print("Loading files")
    filesize = load_files(folder_path, root_entry, HEADER_SIZE)
    #print("Setting up values")
    set_offsets(root_entry, HEADER_SIZE, 0)
    #print(G_file_count, G_dir_count, filesize)
    print_everything(root_entry)

    d = os.path.dirname(folder_path)
    #print("Writing")
    save_tree(d+".VDK", root_entry, filesize)


    return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="folder_to_vdk", description="Creates a VDISK1.0 file from a folder")
    parser.add_argument("folder_path", metavar="FOLDER")
    args = parser.parse_args()
    if "folder_path" in args:
        run(args.folder_path)
    else:
        parser.print_help()