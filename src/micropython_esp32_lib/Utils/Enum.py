"""
# file: ./Utils/Enum.py
"""
import abc

try:
  from ..Utils import Utils
except ImportError:
  import micropython_esp32_lib.Utils.Utils as Utils

class Unit(abc.ABC):
  def __init__(self, name: str, value: int):
    """
    Initialize a Code object with a name and code.

    Args:
      name  (str): The name of the value.
      value (int): The value associated with the name.

    Attributes:
      name  (str): The name of the value.
      value (int): The value associated with the name.
    """
    self.name : str = name
    self.value: int = value
  def __str__(self) -> str:
    return self.name
  def __repr__(self) -> str:
    return f"Unit({self.name}, {self.value})"
  @abc.abstractmethod
  def __eq__(self, other) -> bool:
    if isinstance(other, Unit):
      return self.value == other.value
    return False  
  def __ne__(self, other) -> bool:
    return not self.__eq__(other)