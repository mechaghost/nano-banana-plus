"""Pre-download the rembg U2-Net model during build."""
import os
os.environ.setdefault("U2NET_HOME", "/app/.u2net")
from rembg import new_session
new_session("u2net")
print("rembg U2-Net model cached to", os.environ["U2NET_HOME"])
