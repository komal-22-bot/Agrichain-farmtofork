import hashlib
import json
from datetime import datetime

class Blockchain:
    def __init__(self):
        self.chain = []
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = {
            "index": 1,
            "timestamp": str(datetime.now()),
            "data": "Genesis Block",
            "previousHash": "0",
        }
        genesis_block["currentHash"] = self.hash_block(genesis_block)
        self.chain.append(genesis_block)

    def hash_block(self, block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def add_block(self, data):
        previous_block = self.chain[-1]

        new_block = {
            "index": len(self.chain) + 1,
            "timestamp": str(datetime.now()),  # ✅ real time
            "data": data,
            "previousHash": previous_block["currentHash"],  # ✅ correct linking
        }

        new_block["currentHash"] = self.hash_block(new_block)

        self.chain.append(new_block)

        return new_block