import queue
import socket
import threading

from packages.config import config
from packages.logger import logger

import librosa
import numpy as np

SAMPLE_RATE = 44100
BUFFER_SIZE = 65536
FREQUENCY = 220

socket_queues = {}
socket_steps = {}
client_sockets = {}
send_threads = {}
recv_threads = {}


def close_client_socket(client_addr):
    """
    Close the client socket and clear the client information
    :param client_addr: client address
    """
    client_sockets[client_addr[0]].close()
    if client_addr[0] in socket_queues:
        socket_queues.pop(client_addr[0])
        socket_steps.pop(client_addr[0])
    print(client_addr, "is disconnected")
    logger.info("%s is disconnected", str(client_addr))


def send_audio(client_addr):
    """
    Get audio data from received buffer and processed it and send back to the client.
    :param client_addr: client address
    """
    # Initialize the frame data that received before
    prev_frame = b""
    while True:
        try:
            # Get frame from the buffer
            frame = socket_queues[client_addr[0]].get()
            # Join with the previous frames to convert voice smoothly
            total_frame = prev_frame + frame
            # Convert byte array to numpy ndarray
            audio_np = np.frombuffer(total_frame, dtype=np.float32)
            # process pitch conversion
            processed_audio = process_audio(audio_np, SAMPLE_RATE, socket_steps[client_addr[0]])
            # convert numpy ndarray result to bytes array
            processed_audio_bytes = processed_audio.tobytes()
            # send result back to client
            client_sockets[client_addr[0]].sendall(processed_audio_bytes[len(prev_frame):])
            # update previous frame
            prev_frame = frame
        except Exception as e:
            print(str(e))
            logger.error(str(e))
            close_client_socket(client_addr)
            break


def process_audio(audio_data, sr, n_steps):
    """
    Process pitch conversion
    :param audio_data: source audio data to convert pitch
    :param sr: sample rate
    :param n_steps: pitch conversion level
    :return: pitch conversion result audio data
    """
    # Pitch shifting
    audio_lower_pitch = librosa.effects.pitch_shift(audio_data, sr=sr, n_steps=n_steps)
    return audio_lower_pitch


def recv_audio(client_addr):
    """
    Receive audio data from client and save it into buffer
    :param client_addr: client address
    """
    while True:
        try:
            data = client_sockets[client_addr[0]].recv(BUFFER_SIZE)
            socket_queues[client_addr[0]].put(data)
        except Exception as e:
            print(str(e))
            logger.error(str(e))
            close_client_socket(client_addr)
            return


# create socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)

# host the udp server
server_socket.bind((config["host_address"], (config["host_port"])))
server_socket.listen(10)

# initialize librosa
y = librosa.tone(FREQUENCY, sr=SAMPLE_RATE, length=SAMPLE_RATE)
process_audio(y, SAMPLE_RATE, -3)

print("wait for clients...")
logger.info("wait for clients...")

while True:
    connected_socket, addr = server_socket.accept()
    print(addr, "is connected")
    logger.info("%s is connected", str(addr))

    if addr[0] in socket_queues:
        socket_queues.pop(addr[0])
        socket_steps.pop(addr[0])
        client_sockets[addr[0]].close()
        send_threads[addr[0]].join()
        recv_threads[addr[0]].join()

    steps = connected_socket.recv(1)
    socket_queues[addr[0]] = queue.Queue(-1)
    socket_steps[addr[0]] = int.from_bytes(steps, "little", signed=True)
    client_sockets[addr[0]] = connected_socket
    recv_thread = threading.Thread(target=recv_audio, args=(addr,))
    send_thread = threading.Thread(target=send_audio, args=(addr,))
    send_threads[addr[0]] = send_thread
    recv_threads[addr[0]] = recv_thread
    recv_thread.start()
    send_thread.start()
