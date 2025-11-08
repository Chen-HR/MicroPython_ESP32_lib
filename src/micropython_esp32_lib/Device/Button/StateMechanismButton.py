# src/micropython_esp32_lib/Device/Button/StateMechanismButton.py
import machine
import _thread as thread # For starting synchronous event handlers
import asyncio # For starting asynchronous event handlers

try:
  from ...System import Time
  from ...System import Sleep
  from ...Utils import Logging
  from ...System import Digital
  from ...Utils import EventHandler
  from ...System import Timer
  from ...Utils import Enum
  from ...Utils import Utils
except ImportError:
  # Fallback for direct execution/testing outside the package structure
  from micropython_esp32_lib.System import Time
  from micropython_esp32_lib.System import Sleep
  from micropython_esp32_lib.Utils import Logging
  from micropython_esp32_lib.System import Digital
  from micropython_esp32_lib.Utils import EventHandler
  from micropython_esp32_lib.System import Timer
  from micropython_esp32_lib.Utils import Enum
  from micropython_esp32_lib.Utils import Utils

class BasicState(Enum.Unit):
  pass
class BASICSTATE:
  BOUNCING = BasicState("BOUNCING", 0)
  RELEASED = BasicState("RELEASED", 1)
  PRESSED = BasicState("PRESSED", 2)

class Button:
  def __init__(self, 
               pin: machine.Pin, 
               pressed_signal: Digital.Signal, 
               released_signal: Digital.Signal, 
               debounce_ms: int = 50, # Time to stabilize pin input
               longPress_timeout_ms: int = 500, # Time for a long press to be detected
               multiClick_window_ms: int = 500, # Time window for subsequent clicks in a multi-click sequence
               irq_agent_interval_ms: int = 10, # Interval for the IRQ agent to poll the IRQ flag
               log_name: str = "StateMechanismButton", 
               log_level: Logging.Level = Logging.LEVEL.INFO) -> None:
    
    self.pin: machine.Pin = pin
    self.pressed_signal: Digital.Signal = pressed_signal
    self.released_signal: Digital.Signal = released_signal
    
    self.debounce_ms: int = debounce_ms
    self.longPress_timeout_ms: int = longPress_timeout_ms
    self.multiClick_window_ms: int = multiClick_window_ms
    self.irq_agent_interval_ms: int = irq_agent_interval_ms

    self.logger = Logging.Log(log_name, log_level)
    self.logger.warning("`micropython_esp32_lib.Device.Button.StateMechanismButton.py` does not work properly, it is recommended to use the instant asynchronous version")
    self.logger.debug(f"Button initialized with debounce: {debounce_ms}ms, longPress timeout: {longPress_timeout_ms}ms, multiClick window: {multiClick_window_ms}ms, IRQ agent interval: {irq_agent_interval_ms}ms.")
  
    # Internal state and flags
    self._last_state: BasicState = BASICSTATE.RELEASED
    self._current_state: BasicState = BASICSTATE.RELEASED
    self._last_irq_time_ms: int = 0 

    # Event flags
    self._irq_flag: bool = False # IRQ flag, used to transfer signal from IRQ to the async task
    self._on_press_flag: bool = False
    self._on_release_flag: bool = False
    self._on_longPress_flag: bool = False

    # Event related values
    self._press_start_time_ms: int = 0
    self._last_press_duration_ms: int = 0
    self._multiClick_count: int = 0

    # Internal task reference for IRQ agent
    self._irq_agent_task: asyncio.Task | None = None # Reference to the IRQ agent task

    self._debounce_timer = Timer.AsyncTimer(interval_ms=self.debounce_ms, callback=self._bounced_callback, start=False, log_name=f"{log_name}.DebounceTimer", log_level=log_level)
    self._longPress_timer = Timer.AsyncTimer(interval_ms=self.longPress_timeout_ms, callback=self._longPress_callback, start=False, log_name=f"{log_name}.LongPressTimer", log_level=log_level)

    # Ensure timers are deinitialized initially
    self._stop_all_timers()

    # Configure pin interrupt: trigger on both rising and falling edges
    self.pin.irq(trigger=machine.Pin.IRQ_RISING | machine.Pin.IRQ_FALLING, handler=self._irq_handler)
    self.logger.info(f"Button initialized on pin {pin}. Debounce: {debounce_ms}ms, LongPress: {longPress_timeout_ms}ms, MultiClickWindow: {multiClick_window_ms}ms.")

    self.EventHandlers: list[EventHandler.EventHandler] = [] # For external event listeners

  def _stop_all_timers(self) -> None:
    """Deinitializes all internal timers if they are active."""
    self._debounce_timer.stop()
    self._longPress_timer.stop()
    self.logger.debug("All internal timers deinitialized.")

  def _irq_handler(self, pin: machine.Pin) -> None:
    # self.logger.debug("IRQ flag detected by agent. Restarting debounce timer.")
    self._last_irq_time_ms = Time.current_ms()
    self._current_state = BASICSTATE.BOUNCING
    # Set flag to be handled by the async agent
    self._irq_flag = True 
    
  async def _irq_agent(self) -> None:
    """Async task to safely handle IRQ events and restart timers."""
    while True:
      self.logger.debug("IRQ agent tasking...")
      if self._irq_flag:
        self.logger.debug("IRQ flag detected by agent. Restarting debounce timer.")
        self._irq_flag = False
        # Restart the debounce timer in the asyncio context
        # self._debounce_timer.restart() 
      await Sleep.async_ms(self.irq_agent_interval_ms) # Use the configured polling interval

  def _bounced_callback(self) -> None:
    """Called by the debounce timer upon expiry."""
    self.logger.debug("Debounce timer callback triggered.")
    current_time_ms = Time.current_ms()
    current_signal = Digital.Signal("current", self.pin.value())
    # Determine the stable state after debounce
    current_state: BasicState = BasicState("current", 1 if current_signal == self.released_signal else 2 if current_signal == self.pressed_signal else 0)

    if current_state == BASICSTATE.BOUNCING:
      self.logger.warning(f"Stable pin value after debounce is unexpected: {current_signal}. Expected {self.pressed_signal} or {self.released_signal}.")
      return
    
    if current_state == self._last_state:
      self.logger.debug(f"No state change after debounce. Stable state remains: {self._current_state}.")
      return
      
    if current_state == BASICSTATE.PRESSED and self._last_state == BASICSTATE.RELEASED:
      self.logger.info("Button state stable: PRESSED")
      self._current_state = BASICSTATE.PRESSED
      self._on_press_flag = True

      self._press_start_time_ms = current_time_ms
      self._last_press_duration_ms = 0
      self._longPress_timer.restart()
      self._last_state = BASICSTATE.PRESSED
      return
      
    if current_state == BASICSTATE.RELEASED and self._last_state == BASICSTATE.PRESSED:
      self.logger.info("Button state stable: RELEASED")
      self._current_state = BASICSTATE.RELEASED
      self._on_release_flag = True
      
      # Clear long-press flag when released
      self._on_longPress_flag = False

      self._last_press_duration_ms = current_time_ms - self._press_start_time_ms
      self._press_start_time_ms = 0
      self._longPress_timer.stop()

      # Start single-shot timer for multi-click window
      self._multiClick_count += 1
      def decrement_multiClick_count():
        if self._multiClick_count > 0:
          self._multiClick_count -= 1
      Timer.AsyncTimer(interval_ms=self.multiClick_window_ms, callback=decrement_multiClick_count, repeat=False, start=True, log_name="MultiClickWindowTimer")
      
      self._last_state = BASICSTATE.RELEASED
      return
      
  def _longPress_callback(self) -> None:
    """Called by the long-press timer upon expiry."""
    self.logger.debug("Long press timer callback triggered.")
    # Check if still pressed and the press duration meets the timeout
    if self._current_state == BASICSTATE.PRESSED and Time.current_ms() - self._press_start_time_ms >= self.longPress_timeout_ms:
      self.logger.info(f"Long press detected ({self.longPress_timeout_ms}ms).")
      self._on_longPress_flag = True


  # --- Public Getters for Event Handlers ---
  def get_on_press_flag(self) -> bool:
    """Returns True if a press event occurred and clears the flag."""
    if self._on_press_flag:
      self._on_press_flag = False
      return True
    return False

  def get_on_release_flag(self) -> bool:
    """Returns True if a release event occurred and clears the flag."""
    if self._on_release_flag:
      self._on_release_flag = False
      return True
    return False
  def get_on_longPress_flag(self) -> bool:
    """Returns True if a long press event occurred and clears the flag."""
    if self._on_longPress_flag:
      # NOTE: Flag is cleared on button release, not on read to allow single event trigger.
      return True 
    return False
  def get_last_press_duration_ms(self) -> int:
    """Returns the duration of the last stable press."""
    return self._last_press_duration_ms
  def get_multiClick_count(self) -> int:
    """Returns the current multi-click count (not finalized)."""
    return self._multiClick_count
  
  # --- EventHandler Integration ---
  def addEventHandler(self, eventHandler: EventHandler.EventHandler):
    """Add event handler"""
    if not isinstance(eventHandler, EventHandler.EventHandler):
      raise TypeError("eventHandler must be an instance of EventHandler.EventHandler")
    self.EventHandlers.append(eventHandler)
    return self

  def startEventHandlers_sync(self) -> None:
    """Start all event handlers in sync mode"""
    self.logger.warning("Starting synchronous event handlers will attempt to create multiple threads. "
                        "MicroPython's _thread module on ESP32 may have limitations (e.g., 1-2 user threads). "
                        "This may result in OSError: can't create thread.")
    self.logger.info("Starting all event handlers in sync mode")
    for eh in self.EventHandlers:
      eh.start_sync(self)
  
  async def startEventHandlers_async(self) -> None:
    """Start all event handlers in async mode"""
    self.logger.info("Starting all event handlers in async mode")
    
    # START THE IRQ AGENT TASK
    if self._irq_agent_task is None:
        self._irq_agent_task = asyncio.create_task(self._irq_agent())
        self.logger.debug("IRQ Agent task started.")
        
    for eh in self.EventHandlers:
      eh.start_async(self)

  def stopEventHandlers(self) -> None:
    """Stop all event handlers"""
    self.logger.info("Stopping all event handlers")
    
    # STOP THE IRQ AGENT TASK
    if self._irq_agent_task:
        self._irq_agent_task.cancel()
        self._irq_agent_task = None
        self.logger.debug("IRQ Agent task cancelled.")
        
    # Deinitialize internal timers
    self._stop_all_timers()
    # Disable the pin IRQ to prevent further interrupts
    self.pin.irq(handler=None)
    # Stop external event handlers (which will cancel their tasks/threads)
    for eh in self.EventHandlers:
      eh.stop()

  def __del__(self) -> None:
    """Ensure all resources are cleaned up on object deletion."""
    self.stopEventHandlers()
    self.logger.info("Button object deleted and resources cleaned up.")

class OnPressEvent(EventHandler.Event):
  def __init__(self, object: Button, log_name: str = "Button.OnPressEvent", log_level: Logging.Level = Logging.LEVEL.INFO, *args, **kwargs):
    super().__init__(object, *args, **kwargs)
    self.object: Button = object
    self.logger = Logging.Log(f"{log_name}.{self.object.logger.name}", log_level)
  def monitor_sync(self) -> bool:
    result = self.object.get_on_press_flag()
    self.logger.debug(f"OnPressEvent.monitor_sync: {result}")
    return result
  async def monitor_async(self) -> bool:
    result = self.object.get_on_press_flag() 
    self.logger.debug(f"OnPressEvent.monitor_async: {result}")
    return result

class OnReleaseEvent(EventHandler.Event):
  def __init__(self, object: Button, log_name: str = "Button.OnReleaseEvent", log_level: Logging.Level = Logging.LEVEL.INFO, *args, **kwargs):
    super().__init__(object, *args, **kwargs)
    self.object: Button = object
    self.logger = Logging.Log(f"{log_name}.{self.object.logger.name}", log_level)
  def monitor_sync(self) -> bool:
    result = self.object.get_on_release_flag()
    self.logger.debug(f"OnReleaseEvent.monitor_sync: {result}")
    return result
  async def monitor_async(self) -> bool:
    result = self.object.get_on_release_flag()
    self.logger.debug(f"OnReleaseEvent.monitor_async: {result}")
    return result

class OnLongPressEvent(EventHandler.Event):
  def __init__(self, object: Button, log_name: str = "Button.OnLongPressEvent", log_level: Logging.Level = Logging.LEVEL.INFO, *args, **kwargs):
    super().__init__(object, *args, **kwargs)
    self.object: Button = object
    self.logger = Logging.Log(f"{log_name}.{self.object.logger.name}", log_level)
  def monitor_sync(self) -> bool:
    result = self.object.get_on_longPress_flag()
    self.logger.debug(f"OnLongPressEvent.monitor_sync: {result}")
    return result
  async def monitor_async(self) -> bool:
    result = self.object.get_on_longPress_flag()
    self.logger.debug(f"OnLongPressEvent.monitor_async: {result}")
    return result

class OnMultiClickEvent(EventHandler.Event):
  def __init__(self, object: Button, min_clicks: int, max_clicks: int = 0, log_name: str = "Button.OnMultiClickEvent", log_level: Logging.Level = Logging.LEVEL.INFO, *args, **kwargs):
    super().__init__(object, *args, **kwargs)
    self.object: Button = object
    self.min_clicks: int = min_clicks
    # Ensure max_clicks is at least min_clicks if provided, or defaults to min_clicks for exact match
    self.max_clicks: int = max_clicks if max_clicks >= min_clicks else min_clicks 
    self.logger = Logging.Log(f"{log_name}.{self.object.logger.name}", log_level)
    if min_clicks <= 0:
      self.logger.warning(f"Invalid min_clicks: {min_clicks}. Must be > 0.")

  def monitor_sync(self) -> bool:
    multiClick_count = self.object.get_multiClick_count()
    if multiClick_count > 0: # Only process if there was a finalized click event
      self.logger.debug(f"OnMultiClickEvent.monitor_sync - Finalized count: {multiClick_count}, Min: {self.min_clicks}, Max: {self.max_clicks}")
      if self.min_clicks <= multiClick_count and (self.max_clicks == 0 or multiClick_count <= self.max_clicks):
        return True
    return False

  async def monitor_async(self) -> bool:
    multiClick_count = self.object.get_multiClick_count()
    if multiClick_count > 0: # Only process if there was a finalized click event
      self.logger.debug(f"OnMultiClickEvent.monitor_async - Finalized count: {multiClick_count}, Min: {self.min_clicks}, Max: {self.max_clicks}")
      if self.min_clicks <= multiClick_count and (self.max_clicks == 0 or multiClick_count <= self.max_clicks):
        return True
    return False

if __name__ == "__main__":
  import asyncio
  from micropython_esp32_lib.Utils.Utils import Counter

  class TestHandler(EventHandler.Handler):
    """A concrete Handler to execute button event logic."""
    def __init__(self, button_name: str, event_type: str, counter: 'Counter | None' = None):
      super().__init__(None) # No object needed for this generic handler
      self.button_name: str = button_name
      self.event_type: str = event_type
      self.counter: Counter = counter if counter is not None else Counter(f"Counter.{event_type}")
      self.logger = Logging.Log(f"TestHandler.{event_type}", Logging.LEVEL.INFO)
      
    def handle_sync(self) -> None:
      """Synchronous event execution."""
      self.counter.increment()
      self.logger.info(f"[{self.button_name}] {self.event_type} detected {self.counter.get()} times")
      
    async def handle_async(self) -> None:
      """Asynchronous event execution."""
      self.logger.debug(f"Async handling {self.event_type} for {self.button_name}")
      self.handle_sync()
      await Sleep.async_ms(1) # Small delay to yield control

  # --- Configuration ---
  PIN_A = 19 
  PIN_B = 20
  PIN_C = 21
  DEBOUNCE_MS = 300
  LONGPRESS_TIMEOUT = 1000
  MULTICLICK_WINDOW = 1000
  MULTICLICK_MIN_CLICKS = 2 # For Double Click
  MULTICLICK_MAX_CLICKS = 2 # For Double Click (exact match)
  IRQ_AGENT_INTERVAL_MS = 10 # Agent task polling interval (e.g., 10ms)
  
  # Assuming active-low button with PULL_UP
  PRESSED_SIGNAL: Digital.Signal = Digital.SIGNAL.LOW  
  RELEASED_SIGNAL: Digital.Signal = Digital.SIGNAL.HIGH 

  # --- Button Initialization ---
  button_a = Button(machine.Pin(PIN_A, machine.Pin.IN, machine.Pin.PULL_UP), PRESSED_SIGNAL, RELEASED_SIGNAL, DEBOUNCE_MS, LONGPRESS_TIMEOUT, MULTICLICK_WINDOW, irq_agent_interval_ms=IRQ_AGENT_INTERVAL_MS, log_name="Button.A", log_level=Logging.LEVEL.DEBUG)
  button_b = Button(machine.Pin(PIN_B, machine.Pin.IN, machine.Pin.PULL_UP), PRESSED_SIGNAL, RELEASED_SIGNAL, DEBOUNCE_MS, LONGPRESS_TIMEOUT, MULTICLICK_WINDOW, irq_agent_interval_ms=IRQ_AGENT_INTERVAL_MS, log_name="Button.B", log_level=Logging.LEVEL.DEBUG)
  button_c = Button(machine.Pin(PIN_C, machine.Pin.IN, machine.Pin.PULL_UP), PRESSED_SIGNAL, RELEASED_SIGNAL, DEBOUNCE_MS, LONGPRESS_TIMEOUT, MULTICLICK_WINDOW, irq_agent_interval_ms=IRQ_AGENT_INTERVAL_MS, log_name="Button.C", log_level=Logging.LEVEL.DEBUG)

  # --- Event Handler Setup ---
  # Button A: Full suite of events
  button_a.addEventHandler(EventHandler.EventHandler(OnPressEvent(button_a), TestHandler("Button A", "Press", Counter("ButtonA_Press"))))\
          .addEventHandler(EventHandler.EventHandler(OnReleaseEvent(button_a), TestHandler("Button A", "Release", Counter("ButtonA_Release"))))\
          .addEventHandler(EventHandler.EventHandler(OnLongPressEvent(button_a), TestHandler("Button A", "LongPress", Counter("ButtonA_LongPress"))))\
          .addEventHandler(EventHandler.EventHandler(OnMultiClickEvent(button_a, MULTICLICK_MIN_CLICKS, MULTICLICK_MAX_CLICKS), TestHandler("Button A", "DoubleClick", Counter("ButtonA_DoubleClick"))))
  
  # Button B: Different counter setup (e.g., counting down for release)
  button_b.addEventHandler(EventHandler.EventHandler(OnPressEvent(button_b), TestHandler("Button B", "Press", Counter("ButtonB_Press"))))\
          .addEventHandler(EventHandler.EventHandler(OnReleaseEvent(button_b), TestHandler("Button B", "Release", Counter("ButtonB_Release"))))\
          .addEventHandler(EventHandler.EventHandler(OnLongPressEvent(button_b), TestHandler("Button B", "LongPress", Counter("ButtonB_LongPress"))))\
          .addEventHandler(EventHandler.EventHandler(OnMultiClickEvent(button_b, MULTICLICK_MIN_CLICKS, MULTICLICK_MAX_CLICKS), TestHandler("Button B", "DoubleClick", Counter("ButtonB_DoubleClick"))))

  # Button C: Only Press and Long Press
  button_c.addEventHandler(EventHandler.EventHandler(OnPressEvent(button_c), TestHandler("Button C", "Press", Counter("ButtonC_Press"))))\
          .addEventHandler(EventHandler.EventHandler(OnLongPressEvent(button_c), TestHandler("Button C", "LongPress", Counter("ButtonC_LongPress"))))

  logger = Logging.Log(name="main", level=Logging.LEVEL.INFO)

  # --- Asynchronous Test Block (Recommended) ---
  logger.info("\n\n")
  try:
    logger.info("Testing StateMechanismButton class with asynchronous (Asyncio) mode. ")
    logger.info("  (Events are detected via Pin IRQ -> IRQ Agent -> Timers.) ")
    logger.info("  (Press Ctrl+C to stop the program.)")


    async def main_async_test():
      await button_a.startEventHandlers_async()
      await button_b.startEventHandlers_async()
      await button_c.startEventHandlers_async()
      # Keep the asyncio scheduler running
      while True: await Sleep.async_ms(100) 
      
    asyncio.run(main_async_test())
    
  except KeyboardInterrupt:
    logger.info("Program interrupted")
  finally:
    button_a.stopEventHandlers()
    button_b.stopEventHandlers()
    button_c.stopEventHandlers()
    logger.info("Asynchronous monitors stopped.")

  # --- Synchronous Test Block (Warning: Limited thread support on ESP32) ---
  logger.info("\n\n")

  try:
    logger.info("Testing StateMechanismButton class with synchronous (Thread) mode. ")
    logger.info("  (WARNING: Not recommended. MicroPython on ESP32 has limited thread support and this may fail with OSError: can't create thread.)")
    logger.info("  (Starting only one button to minimize thread risk.)")
    
    # Only start one button to prevent thread exhaustion
    button_a.startEventHandlers_sync()
    
    while True: Sleep.sync_ms(100)
  except KeyboardInterrupt:
    logger.info("Program interrupted")
  except OSError as e:
    logger.error(f"Synchronous test failed: {e}. Too many threads created.")
  finally:
    button_a.stopEventHandlers() 
    logger.info("Synchronous monitors stopped.")

  logger.info("Program ended.")