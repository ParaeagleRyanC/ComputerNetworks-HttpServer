import logging
import socket
import argparse
import os
import time
from signal import signal, SIGPIPE, SIG_DFL

# takes care of BrokenPipeError
signal(SIGPIPE, SIG_DFL)

WAIT_TIME = 5
DEFAULT_RECEIVE_SIZE = 1024
END_OF_HEADER_OR_REQUEST = "\r\n\r\n"
END_OF_REQUEST_LENGTH = 4
COMMON_HEADER = "content-Length: "
METHOD_NOT_ALLOWED = "HTTP/1.1 405 Method Not Allowed\r\n" + COMMON_HEADER
SUCCESS = "HTTP/1.1 200 OK\r\n" + COMMON_HEADER
NOT_FOUND = "HTTP/1.1 404 Page Not Found\r\n" + COMMON_HEADER


def send_response(conn, file_path, header):
    send_number = 0
    # only deal with file if file_path is given
    if file_path:
        # header part
        file_size = os.path.getsize(root_folder + file_path)
        logging.info(f"File size is: {file_size}")
        response_header = header + str(file_size) + END_OF_HEADER_OR_REQUEST
        conn.send(response_header.encode())

        # actual file to return to client
        f = open(root_folder + file_path, "rb")
        # loop until EOF is reached
        while True:
            file_content = f.read(DEFAULT_RECEIVE_SIZE)
            if not file_content:
                break
            conn.sendall(file_content)
            send_number += 1
            logging.info(send_number)
    else:
        conn.send((header + "0" + END_OF_HEADER_OR_REQUEST).encode())


def get_header(code):
    if code == 200:
        return SUCCESS
    if code == 404:
        return NOT_FOUND
    if code == 405:
        return METHOD_NOT_ALLOWED


def is_request_file_exist(request_file):
    return os.path.isfile(root_folder + request_file)


def process_request(conn, request):
    first_line = request[0 : request.index("\r\n")]
    info = first_line.split(" ")
    method = info[0]
    request_file = info[1]

    # return 405 Method Not Allowed
    if method != "GET":
        send_response(conn, 0, get_header(405))
        return

    # check if the reqeusted file is the default file
    if request_file == "/":
        send_response(conn, "/page.html", get_header(200))
        return

    # check if requested file exists
    if not is_request_file_exist(request_file):
        send_response(conn, "/404.html", get_header(404))
        return

    # otherwise return the requested file
    send_response(conn, request_file, get_header(200))


# function to run non-stop until KeyboardInterrupt
def run(port):
    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("", port))
    server_socket.listen()
    logging.info(f"Listening on port {port}")

    data_string = ""

    # loop forever until KeyboardInterrupt is detected (Exception thrown)
    while True:
        conn, address = server_socket.accept()
        logging.info(f"Connection from: {address}")

        # loop until current client disconnects
        while True:
            # this try-except block is for catching ConnectionResetError
            try:
                data = conn.recv(DEFAULT_RECEIVE_SIZE).decode()
            except ConnectionResetError:
                logging.info("Client disconnected...")
                data_string = ""
                break

            # if data is 0, meaning client disconnected, up one level and wait
            if not data:
                logging.info("Client disconnected...")
                data_string = ""
                break

            data_string += data
            logging.info(f"Received: {data}")
            logging.info(f"Current Data String:\n{data_string}")

            # check if "/r/n/r/n" is in the request
            if END_OF_HEADER_OR_REQUEST in data:
                end_of_request_index = data_string.index(END_OF_HEADER_OR_REQUEST)
                request = data_string[0:end_of_request_index]
                logging.info(f"Complete request received:\n{request}")
                data_string = data_string[
                    end_of_request_index + END_OF_REQUEST_LENGTH :
                ]
                # wait 5 seconds before processing the request
                if args.delay:
                    time.sleep(WAIT_TIME)
                process_request(conn, request)


# function to parse arguments
def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        required=False,
        default=8084,
        help="port to bind to",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        required=False,
        action="store_true",
        help="turn on debugging output",
    )
    parser.add_argument(
        "-d",
        "--delay",
        required=False,
        action="store_true",
        help="add a delay for debugging purposes",
    )
    parser.add_argument(
        "-f",
        "--folder",
        type=str,
        required=False,
        default=".",
        help="folder from where to serve from",
    )
    return parser.parse_args()


# main function
if __name__ == "__main__":
    global root_folder
    args = parse_arguments()
    root_folder = args.folder
    # if verbose flag is high, turn on verbose
    if args.verbose:
        logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
    # this try-except block is for catching KeyboardInterrupt
    try:
        run(args.port)
    except KeyboardInterrupt:
        logging.info("Keyboard Interrupt Detected!")
