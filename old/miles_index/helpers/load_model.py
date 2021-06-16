import msgpack
import msgpack_numpy as m
import numpy as np
import json
m.patch()

from miles_index.redis import r

known_face_encodings = m.unpackb(r.get('known_face_encodings'))
profiles = json.loads(r.get('profiles'))
