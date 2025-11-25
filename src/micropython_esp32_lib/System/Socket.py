"""
# file: ./System/Socket.py

- https://docs.python.org/3.8/library/asyncio-stream.html#asyncio.start_server
"""
import abc
import usocket
import uasyncio

try: 
  from ..Utils import Logging
  from ..Utils import Enum
except ImportError:
  from micropython_esp32_lib.Utils import Logging
  from micropython_esp32_lib.Utils import Enum

class AdderssFamily(Enum.Unit):
  def __init__(self, name: str, id: int):
    super().__init__(name, id)
  def __repr__(self) -> str:
    return f"AdderssType({self.name}, {self.value})"
  def __eq__(self, other) -> bool:
    if isinstance(other, AdderssFamily): return self.value == other.value
    return False
class ADDRESSFAMILY:
  INET = AdderssFamily("inet", usocket.AF_INET)
  INET6 = AdderssFamily("inet6", usocket.AF_INET6)

class SocketType(Enum.Unit): # socket types
  def __init__(self, name: str, id: int):
    super().__init__(name, id)
  def __repr__(self) -> str:
    return f"SocketType({self.name}, {self.value})"
  def __eq__(self, other) -> bool:
    if isinstance(other, SocketType): return self.value == other.value
    return False
class SOCKETTYPE:
  STREAM = SocketType("STREAM", usocket.SOCK_STREAM)
  DATAGRAM = SocketType("DATAGRAM", usocket.SOCK_DGRAM)

class IPProtocol(Enum.Unit):
  def __init__(self, name: str, id: int):
    super().__init__(name, id)
  def __repr__(self) -> str:
    return f"IPProtocol({self.name}, {self.value})"
  def __eq__(self, other) -> bool:
    if isinstance(other, IPProtocol): return self.value == other.value
    return False
class IPPROTOCOL:
  TCP = IPProtocol("TCP", usocket.IPPROTO_TCP)
  UDP = IPProtocol("UDP", usocket.IPPROTO_UDP)

class SocketOptionLevel: # socket option level
  def __init__(self, level: int):
    self.value = level
  def __repr__(self) -> str:
    return f"SocketOptionLevel({self.value})"
  def __eq__(self, other) -> bool:
    if isinstance(other, SocketOptionLevel): return self.value == other.value
    return False
# class SOCKETOPTIONLEVEL:
#   SOL_SOCKET = SocketOptionLevel(usocket.SOL_SOCKET)
SOCKETOPTIONLEVEL = SocketOptionLevel(usocket.SOL_SOCKET)

class SocketOption(Enum.Unit): # socket option
  def __init__(self, name: str, code: int):
    super().__init__(name, code)
  def __repr__(self) -> str:
    return f"SocketOption({self.name}, {self.value})"
  def __eq__(self, other) -> bool:
    if isinstance(other, SocketOption): return self.value == other.value
    return False
class SOCKETOPTION:
  
  REUSEADDR    = SocketOption("REUSEADDR", 4)
  BROADCAST    = SocketOption("BROADCAST", 32)
  KEEPALIVE    = SocketOption("KEEPALIVE", usocket.SO_KEEPALIVE)
  BINDTODEVICE = SocketOption("BINDTODEVICE", 4107)
  try: 
    REUSEADDR = SocketOption("REUSEADDR", usocket.SO_REUSEADDR)
    BROADCAST = SocketOption("BROADCAST", usocket.SO_BROADCAST)
    KEEPALIVE = SocketOption("KEEPALIVE", usocket.SO_KEEPALIVE)
    BINDTODEVICE = SocketOption("BINDTODEVICE", usocket.SO_BINDTODEVICE) # type: ignore
  except AttributeError:
    tmp=Logging.Log("Network Constants Socket Option", Logging.LEVEL.WARNING)
    tmp.warning("Network socket option constants (`usocket.SO_REUSEADDR`, `usocket.SO_BROADCAST`, `usocket.SO_KEEPALIVE`, `usocket.SO_BINDTODEVICE`) not fully found. Using internal fallbacks.")
    del tmp

class SocketAddress:
  def __init__(self, host: str, port: int):
    self.host = host
    self.port = port
  def __str__(self) -> str:
    return f"{self.host}:{self.port}"
  def __repr__(self) -> str:
    return f"SocketAddress('{self.host}', {self.port})"

class Socket(usocket.socket):
  """
  A synchronous socket wrapper that inherits from usocket.socket, providing
  a consistent interface within the library's framework.
  """
  def __init__(self, family: AdderssFamily = ADDRESSFAMILY.INET, type: SocketType = SOCKETTYPE.STREAM, proto: IPProtocol = IPPROTOCOL.TCP, fileno: int = -1):
    super().__init__(family.value, type.value, proto.value, fileno)
  
  def accept(self) -> tuple[usocket.socket, tuple[str, int]]:
    """Accept a connection. Returns (conn_socket, address_tuple)."""
    return super().accept()
    
  def setsockopt_(self, level: SocketOptionLevel = SOCKETOPTIONLEVEL, option: SocketOption = SOCKETOPTION.REUSEADDR, value: int = 1) -> None:
    """Set a socket option using the library's Enum wrappers."""
    super().setsockopt(level.value, option.value, value)
