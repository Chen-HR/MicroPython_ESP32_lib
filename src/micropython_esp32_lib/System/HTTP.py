"""
# file: ./System/HTTP.py
- https://en.wikipedia.org/wiki/HTTP
- https://en.wikipedia.org/wiki/List_of_HTTP_status_codes

# Sync
- https://docs.micropython.org/en/latest/library/socket.html
- https://realpython.com/python-sockets/
- https://randomnerdtutorials.com/esp32-esp8266-micropython-web-server/

# Async
- https://docs.micropython.org/en/latest/library/asyncio.html
- https://github.com/orgs/micropython/discussions/13590

"""

import usocket
import abc
import uasyncio
import inspect

try: 
  from ..Utils import Logging
  from ..Utils import Enum
  from ..System import Network
  from ..System import WiFi # For the example
except ImportError:
  from micropython_esp32_lib.Utils import Logging
  from micropython_esp32_lib.Utils import Enum
  from micropython_esp32_lib.System import Network
  from micropython_esp32_lib.System import WiFi


class Status(Enum.Unit):
  def __init__(self, name: str, code: int):
    super().__init__(name, code)
    self.code = code
  def __eq__(self, other) -> bool:
    if isinstance(other, Status): return self.code == other.code
    return False
class STATUS:
  # 1xx Informational
  CONTINUE              : Status = Status("Continue", 100)
  SWITCHING_PROTOCOLS   : Status = Status("Switching Protocols", 101)
  EARLY_HINTS           : Status = Status("Early Hints", 103)
  # 2xx Success
  OK                    : Status = Status("OK", 200)
  CREATED               : Status = Status("Created", 201)
  ACCEPTED              : Status = Status("Accepted", 202)
  NON_AUTHORITATIVE_INFO: Status = Status("Non-Authoritative Information", 203)
  NO_CONTENT            : Status = Status("No Content", 204)
  RESET_CONTENT         : Status = Status("Reset Content", 205)
  PARTIAL_CONTENT       : Status = Status("Partial Content", 206)
  MULTI_STATUS          : Status = Status("Multi-Status", 207)
  IM_USED               : Status = Status("IM Used", 226)
  # 3xx Redirection
  MULTIPLE_CHOICES      : Status = Status("Multiple Choices", 300)
  MOVED_PERMANENTLY     : Status = Status("Moved Permanently", 301)
  FOUND                 : Status = Status("Found", 302)
  SEE_OTHER             : Status = Status("See Other", 303)
  NOT_MODIFIED          : Status = Status("Not Modified", 304)
  TEMPORARY_REDIRECT    : Status = Status("Temporary Redirect", 307)
  PERMANENT_REDIRECT    : Status = Status("Permanent Redirect", 308)
  # 4xx Client Error
  BAD_REQUEST           : Status = Status("Bad Request", 400)
  UNAUTHORIZED          : Status = Status("Unauthorized", 401)
  PAYMENT_REQUIRED      : Status = Status("Payment Required", 402)
  FORBIDDEN             : Status = Status("Forbidden", 403)
  NOT_FOUND             : Status = Status("Not Found", 404)
  METHOD_NOT_ALLOWED    : Status = Status("Method Not Allowed", 405)
  NOT_ACCEPTABLE        : Status = Status("Not Acceptable", 406)
  PROXY_AUTHENTICATION_REQUIRED: Status = Status("Proxy Authentication Required", 407)
  REQUEST_TIMEOUT       : Status = Status("Request Timeout", 408)
  CONFLICT              : Status = Status("Conflict", 409)
  GONE                  : Status = Status("Gone", 410)
  LENGTH_REQUIRED       : Status = Status("Length Required", 411)
  PRECONDITION_FAILED   : Status = Status("Precondition Failed", 412)
  PAYLOAD_TOO_LARGE     : Status = Status("Payload Too Large", 413)
  URI_TOO_LONG          : Status = Status("URI Too Long", 414)
  UNSUPPORTED_MEDIA_TYPE: Status = Status("Unsupported Media Type", 415)
  RANGE_NOT_SATISFIABLE : Status = Status("Range Not Satisfiable", 416)
  EXPECTATION_FAILED    : Status = Status("Expectation Failed", 417)
  TOO_MANY_REQUESTS     : Status = Status("Too Many Requests", 429)
  HEADER_FIELDS_TOO_LARGE: Status = Status("Request Header Fields Too Large", 431)
  UNAVAILABLE_FOR_LEGAL_REASONS: Status = Status("Unavailable For Legal Reasons", 451)
  # 5xx Server Error
  INTERNAL_SERVER_ERROR : Status = Status("Internal Server Error", 500)
  NOT_IMPLEMENTED       : Status = Status("Not Implemented", 501)
  BAD_GATEWAY           : Status = Status("Bad Gateway", 502)
  SERVICE_UNAVAILABLE   : Status = Status("Service Unavailable", 503)
  GATEWAY_TIMEOUT       : Status = Status("Gateway Timeout", 504)
  VERSION_NOT_SUPPORTED : Status = Status("HTTP Version Not Supported", 505)
  
  _CODE_MAP = {
      100: CONTINUE, 101: SWITCHING_PROTOCOLS, 103: EARLY_HINTS,
      200: OK, 201: CREATED, 202: ACCEPTED, 203: NON_AUTHORITATIVE_INFO, 204: NO_CONTENT, 
      205: RESET_CONTENT, 206: PARTIAL_CONTENT, 207: MULTI_STATUS, 226: IM_USED,
      300: MULTIPLE_CHOICES, 301: MOVED_PERMANENTLY, 302: FOUND, 303: SEE_OTHER, 
      304: NOT_MODIFIED, 307: TEMPORARY_REDIRECT, 308: PERMANENT_REDIRECT,
      400: BAD_REQUEST, 401: UNAUTHORIZED, 402: PAYMENT_REQUIRED, 403: FORBIDDEN, 
      404: NOT_FOUND, 405: METHOD_NOT_ALLOWED, 406: NOT_ACCEPTABLE, 407: PROXY_AUTHENTICATION_REQUIRED,
      408: REQUEST_TIMEOUT, 409: CONFLICT, 410: GONE, 411: LENGTH_REQUIRED, 
      412: PRECONDITION_FAILED, 413: PAYLOAD_TOO_LARGE, 414: URI_TOO_LONG, 
      415: UNSUPPORTED_MEDIA_TYPE, 416: RANGE_NOT_SATISFIABLE, 417: EXPECTATION_FAILED, 
      429: TOO_MANY_REQUESTS, 431: HEADER_FIELDS_TOO_LARGE, 451: UNAVAILABLE_FOR_LEGAL_REASONS,
      500: INTERNAL_SERVER_ERROR, 501: NOT_IMPLEMENTED, 502: BAD_GATEWAY, 
      503: SERVICE_UNAVAILABLE, 504: GATEWAY_TIMEOUT, 505: VERSION_NOT_SUPPORTED
  }

  @classmethod
  def query(cls, code: int) -> Status:
    status = cls._CODE_MAP.get(code)
    if status is None:
        # Return a generic Status object for unsupported codes, based on class
        class_code = code // 100
        if class_code == 1: name = "Informational"
        elif class_code == 2: name = "Success"
        elif class_code == 3: name = "Redirection"
        elif class_code == 4: name = "Client Error"
        elif class_code == 5: name = "Server Error"
        else: raise ValueError(f"Invalid HTTP status code: {code}")
        return Status(f"{name} ({code})", code)
    return status

class Method(Enum.Unit):
  def __init__(self, name: str, id: int):
    super().__init__(name, id)
  def __eq__(self, other) -> bool:
    if isinstance(other, str): return self.name == other.upper()
    return super().__eq__(other)
class METHOD:
  GET    : Method = Method("GET"    , 0)
  POST   : Method = Method("POST"   , 1)
  PUT    : Method = Method("PUT"    , 2)
  DELETE : Method = Method("DELETE" , 3)
  HEAD   : Method = Method("HEAD"   , 4)
  CONNECT: Method = Method("CONNECT", 5)
  OPTIONS: Method = Method("OPTIONS", 6)
  TRACE  : Method = Method("TRACE"  , 7)
  PATCH  : Method = Method("PATCH"  , 8)
  @classmethod
  def query(cls, method: str) -> Method:
    method = method.upper()
    if   method == "GET"    : return cls.GET
    elif method == "POST"   : return cls.POST
    elif method == "PUT"    : return cls.PUT
    elif method == "DELETE" : return cls.DELETE
    elif method == "HEAD"   : return cls.HEAD
    elif method == "CONNECT": return cls.CONNECT
    elif method == "OPTIONS": return cls.OPTIONS
    elif method == "TRACE"  : return cls.TRACE
    elif method == "PATCH"  : return cls.PATCH
    raise ValueError(f"Invalid HTTP method: {method}")

class MIMEType:
  def __init__(self, name: str, mime: str):
    self.name = name
    self.mime = mime
  def __eq__(self, value: object) -> bool:
    if isinstance(value, str): return self.mime == value.lower()
    return super().__eq__(value)
class MIME:
  TEXT : MIMEType = MIMEType("TEXT", "text/plain")
  HTML : MIMEType = MIMEType("HTML", "text/html")
  JSON : MIMEType = MIMEType("JSON", "application/json")
  @classmethod
  def query(cls, mime: str) -> MIMEType:
    mime = mime.lower()
    if   mime == "text/plain": return cls.TEXT
    elif mime == "text/html": return cls.HTML
    elif mime == "application/json": return cls.JSON
    return MIMEType("UNKNOWN", mime)

class Message(abc.ABC):
  def __init__(self, header: dict[str, str], body: str = "", protocol: str = "HTTP/1.1"):
    self.header = header
    self.body = body
    self.protocol = protocol
  @abc.abstractmethod
  def _title(self) -> str:
    pass
  def _header(self) -> str:
    return "\r\n".join([f"{key}: {value}" for key, value in self.header.items()])
  def _body(self) -> str:
    return self.body
  def __str__(self) -> str:
    # Ensure there is a body by adding Content-Length if not present
    if 'Content-Length' not in self.header and self.body:
        self.header['Content-Length'] = str(len(self.body.encode('utf-8')))
    if self.body:
        return "\r\n".join([self._title(), self._header(), "", self._body()])
    else:
        return "\r\n".join([self._title(), self._header(), "\r\n"])
  def pack(self, encoding="utf-8") -> bytes:
    return (self.__str__()).encode(encoding)
  @classmethod
  def unpack(cls, data: bytes, encoding="utf-8") -> "Message": # type: ignore
    pass

class RequestMessage(Message):
  def __init__(self, method: Method, path: str, header: dict[str, str], body: str = "", protocol: str = "HTTP/1.1"):
    super().__init__(header, body, protocol)
    self.method = method
    self.path = path
  def _title(self) -> str:
    return f"{self.method.name} {self.path} {self.protocol}"
  @classmethod
  def unpack(cls, data: bytes, encoding="utf-8") -> "RequestMessage":
    """
    Parses a raw HTTP request from bytes into a RequestMessage object.
    """
    try:
      text = data.decode(encoding)
      parts = text.split('\r\n\r\n', 1)
      header_part = parts[0]
      body = parts[1] if len(parts) > 1 else ""

      header_lines = header_part.split('\r\n')
      request_line = header_lines[0]
      
      method_str, path, protocol = request_line.split(' ', 2)
      method = METHOD.query(method_str)
      
      headers = {}
      for line in header_lines[1:]:
        if ': ' in line:
          key, value = line.split(': ', 1)
          headers[key] = value
          
      return RequestMessage(method=method, path=path, header=headers, body=body, protocol=protocol)
    except (UnicodeDecodeError, IndexError, ValueError) as e:
      raise ValueError(f"Failed to parse invalid HTTP request: {e}")

class ResponseMessage(Message):
  def __init__(self, status: Status, header: dict[str, str], body: str = "", protocol: str = "HTTP/1.1"):
    super().__init__(header, body, protocol)
    self.status = status
  def _title(self) -> str:
    return f"{self.protocol} {self.status.code} {self.status.name}"
  @classmethod
  def unpack(cls, data: bytes, encoding="utf-8") -> "ResponseMessage":
    """
    Parses a raw HTTP response from bytes into a ResponseMessage object.
    """
    try:
      text = data.decode(encoding)
      parts = text.split('\r\n\r\n', 1)
      header_part = parts[0]
      body = parts[1] if len(parts) > 1 else ""

      header_lines = header_part.split('\r\n')
      status_line = header_lines[0]

      protocol, status_code_str, _ = status_line.split(' ', 2)
      status = STATUS.query(int(status_code_str))
      
      headers = {}
      for line in header_lines[1:]:
        if ': ' in line:
          key, value = line.split(': ', 1)
          headers[key] = value

      return ResponseMessage(status=status, header=headers, body=body, protocol=protocol)
    except (UnicodeDecodeError, IndexError, ValueError) as e:
      raise ValueError(f"Failed to parse invalid HTTP response: {e}")

# --- Asynchronous HTTP Server Components ---

class AsyncRequestHandler(abc.ABC):
  """Abstract base class for handling asynchronous HTTP requests."""
  @abc.abstractmethod
  async def handle(self, request: RequestMessage) -> ResponseMessage:
    """
    Processes an incoming RequestMessage and returns a ResponseMessage.

    Args:
      request (RequestMessage): The incoming HTTP request.

    Returns:
      ResponseMessage: The HTTP response to be sent to the client.
    """
    pass

class AsyncRequestResponseHandler(AsyncRequestHandler):
  """A concrete request handler that uses a callback to generate a response."""
  def __init__(self, callback):
    """
    Initializes the handler with a user-defined callback function.

    Args:
      callback (callable): An async function that takes a RequestMessage
                           and returns a ResponseMessage.
    """
    # if not inspect.iscoroutinefunction(callback):
    #   raise TypeError("Callback must be an async function.")
    self._callback = callback

  async def handle(self, request: RequestMessage) -> ResponseMessage:
    return await self._callback(request)

class AsyncRequestRouteHandler(AsyncRequestHandler):
  """
  A request handler that routes requests to other handlers based on path and method.
  Supports nested routing through path prefix matching.
  """
  def __init__(self, log_level: Logging.Level = Logging.LEVEL.INFO):
    # { "GET": {"/path": handler}, "POST": {"/path2": handler} }
    self._routes: dict[str, dict[str, AsyncRequestHandler]] = {}
    self.logger = Logging.Log("AsyncRequestRouteHandler", log_level)

  def add_route(self, path: str, handler: AsyncRequestHandler, method: Method = METHOD.GET):
    """
    Adds a route to the routing table.

    Args:
      path (str): The URL path prefix to match.
      handler (AsyncRequestHandler): The handler to process requests for this route.
      method (Method, optional): The HTTP method for this route. Defaults to METHOD.GET.
    """
    method_name = method.name
    if method_name not in self._routes:
      self._routes[method_name] = {}
    self._routes[method_name][path] = handler
    self.logger.debug(f"Added route: {method_name} {path}")

  async def handle(self, request: RequestMessage) -> ResponseMessage:
    method_routes = self._routes.get(request.method.name, {})
    
    # Find the longest matching path prefix
    best_match_path = ""
    handler = None
    for path, registered_handler in method_routes.items():
      if request.path.startswith(path):
        if len(path) > len(best_match_path):
          best_match_path = path
          handler = registered_handler
          
    if handler:
      self.logger.debug(f"Routing request for '{request.path}' to handler for '{best_match_path}'")
      # Create a new request object with the path stripped of the matched prefix
      # to allow for nested routing.
      modified_request = RequestMessage(
          method=request.method,
          path=request.path[len(best_match_path):],
          header=request.header,
          body=request.body,
          protocol=request.protocol
      )
      return await handler.handle(modified_request)
    else:
      self.logger.warning(f"No route found for {request.method.name} {request.path}")
      return ResponseMessage(
          status=STATUS.NOT_FOUND,
          header={"Content-Type": MIME.TEXT.mime, "Connection": "close"},
          body=f"404 Not Found: {request.path}"
      )

class AsyncServer:
  """An asynchronous HTTP server that listens for and handles connections."""
  def __init__(self, root_handler: AsyncRequestHandler, host: str = '0.0.0.0', port: int = 80, log_level: Logging.Level = Logging.LEVEL.INFO):
    """
    Initializes the asynchronous HTTP server.

    Args:
      root_handler (AsyncRequestHandler): The root handler to process all incoming requests.
      host (str, optional): The host address to bind to. Defaults to '0.0.0.0'.
      port (int, optional): The port to listen on. Defaults to 80.
      log_level (Logging.Level, optional): Logging level. Defaults to Logging.LEVEL.INFO.
    """
    self.root_handler = root_handler
    self.host = host
    self.port = port
    self.logger = Logging.Log(f"AsyncServer({host}:{port})", log_level)
    self._server = None

  async def _handle_connection(self, reader, writer):
    addr = writer.get_extra_info('peername')
    self.logger.info(f"Received connection from {addr}")
    try:
      # Read the request line and headers
      raw_request = await reader.read(1024)
      if not raw_request:
        self.logger.warning("Empty request received.")
        writer.close()
        await writer.wait_closed()
        return

      request = RequestMessage.unpack(raw_request)
      self.logger.debug(f"Request: {request.method.name} {request.path}")
      
      response = await self.root_handler.handle(request)
      
      writer.write(response.pack())
      await writer.drain()
    except ValueError as e:
      self.logger.error(f"Failed to parse request: {e}")
      response = ResponseMessage(
          status=STATUS.BAD_REQUEST,
          header={"Content-Type": MIME.TEXT.mime, "Connection": "close"},
          body="400 Bad Request"
      )
      writer.write(response.pack())
      await writer.drain()
    except Exception as e:
      self.logger.error(f"An error occurred while handling connection: {e}")
      response = ResponseMessage(
          status=STATUS.INTERNAL_SERVER_ERROR,
          header={"Content-Type": MIME.TEXT.mime, "Connection": "close"},
          body="500 Internal Server Error"
      )
      writer.write(response.pack())
      await writer.drain()
    finally:
      writer.close()
      await writer.wait_closed()
      self.logger.info(f"Connection from {addr} closed")

  async def start(self):
    """Starts the asyncio server."""
    if self._server:
      self.logger.warning("Server is already running.")
      return
    self.logger.info(f"Starting server on {self.host}:{self.port}...")
    self._server = await uasyncio.start_server(
        self._handle_connection, self.host, self.port)
    self.logger.info("Server started successfully.")

  async def stop(self):
    """Stops the asyncio server."""
    if self._server:
      self._server.close()
      await self._server.wait_closed()
      self._server = None
      self.logger.info("Server stopped.")

if __name__ == '__main__':
  # This block serves as a comprehensive example of how to use the async server.
  # It requires a MicroPython environment with network capabilities.
  
  # --- 1. Define Handler Functions ---
  async def handle_root(request: RequestMessage) -> ResponseMessage:
    html_content = """
    <html>
      <head><title>MicroPython Server</title></head>
      <body>
        <h1>Welcome!</h1>
        <p>This is the root page.</p>
        <p><a href="/hello">Say Hello</a></p>
        <p><a href="/api/info">View API Info</a></p>
      </body>
    </html>
    """
    return ResponseMessage(
        status=STATUS.OK,
        header={"Content-Type": MIME.HTML.mime},
        body=html_content
    )
    
  async def handle_hello(request: RequestMessage) -> ResponseMessage:
    return ResponseMessage(
        status=STATUS.OK,
        header={"Content-Type": MIME.TEXT.mime},
        body="Hello from the MicroPython server!"
    )
    
  async def handle_api_info(request: RequestMessage) -> ResponseMessage:
    import json
    info_body = json.dumps({"service": "micropython-api", "version": "1.0"})
    return ResponseMessage(
        status=STATUS.OK,
        header={"Content-Type": MIME.JSON.mime},
        body=info_body
    )

  # --- 2. Setup Routing ---
  log_level = Logging.LEVEL.DEBUG
  
  # Create handlers for specific responses
  root_handler = AsyncRequestResponseHandler(handle_root)
  hello_handler = AsyncRequestResponseHandler(handle_hello)
  api_info_handler = AsyncRequestResponseHandler(handle_api_info)
  
  # Create a sub-router for the /api path
  api_router = AsyncRequestRouteHandler(log_level=log_level)
  api_router.add_route("/info", api_info_handler, method=METHOD.GET)
  
  # Create the main router
  main_router = AsyncRequestRouteHandler(log_level=log_level)
  main_router.add_route("/", root_handler, method=METHOD.GET)
  main_router.add_route("/hello", hello_handler, method=METHOD.GET)
  main_router.add_route("/api", api_router) # Nest the API router

  # --- 3. Main async function ---
  async def main():
    main_logger = Logging.Log("HTTP_Server_Example", log_level)
    main_logger.info("Starting up...")
    
    # --- Server Initialization ---
    server = AsyncServer(root_handler=main_router, port=80, log_level=log_level)
    
    try:
      await server.start()
      main_logger.info("Server is running. Press Ctrl+C to stop.")
      # Keep the server running indefinitely
      while True:
        await uasyncio.sleep(10)
    except KeyboardInterrupt:
      main_logger.info("Keyboard interrupt received.")
    finally:
      await server.stop()
      main_logger.info("Cleanup complete. Exiting.")

  # --- 4. Run the application ---
  try:
    uasyncio.run(main())
  except Exception as e:
    # Catch any top-level errors during startup
    Logging.Log("main_runner").error(f"Fatal error: {e}")