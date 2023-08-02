import hashlib
from typing import List


class SHA1Helper:
    def __init__(self):
        self.sha1 = hashlib.sha1()

    def update_str(self, str_list: List[str]):
        for s in str_list:
            self.sha1.update(s.encode())

    def update_file(self, file_list: List[str]):
        for file in file_list:
            with open(file, "r") as f:
                data = f.read()
            self.sha1.update(data.encode())

    def hexdigest(self) -> str:
        return self.sha1.hexdigest()


def sha1_encode(str_list: List[str]):
    # create a SHA1 hash object
    sha1 = hashlib.sha1()
    # update the hash object with the string
    for s in str_list:
        sha1.update(s.encode())
    # get the hexadecimal representation of the hash
    hex_digest = sha1.hexdigest()
    return hex_digest
