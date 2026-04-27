import hashlib
import time

def generate_hash(data):
    return hashlib.sha256(data.encode()).hexdigest()

def create_block(transaction_id, prev_hash):
    data = f"{transaction_id}{prev_hash}{time.time()}"
    hash_val = generate_hash(data)

    return hash_val

