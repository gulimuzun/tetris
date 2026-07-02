from __future__ import annotations

import json
import queue
import socket
import threading
import time
#通过UDP广播发现房间，通过TCP建立房间联系

from .config import DISCOVERY_PORT, GAME_PORT
