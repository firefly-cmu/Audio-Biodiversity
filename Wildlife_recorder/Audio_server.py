import os
import asyncio
import websockets
import soundfile as sf
import numpy as np
from datetime import datetime
from scipy.fft import rfft

# Audio sample rate in Hz (sufficient to capture frequencies up to 8 kHz)
SAMPLE_RATE = 16000

# Dictionary to store audio buffers for each client
client_buffers = {}
# Dictionary to store client identifiers mapped by IP address
client_ids = {}


def spectral_flatness(audio_array):
    """
    Calculate the Spectral Flatness Measure (SFM), which is the ratio between
    the geometric mean and the arithmetic mean of the power spectrum.
    Used to distinguish tonal (e.g. bird) sounds from noise.

    Args:
        audio_array (np.ndarray): The raw audio signal in 1D numpy array.

    Returns:
        float: Spectral flatness value.
    """
    samples = audio_array.astype(np.float32)
    fft_vals = np.abs(rfft(samples)) + 1e-10  # Avoid log(0)
    geo_mean = np.exp(np.mean(np.log(fft_vals)))
    arith_mean = np.mean(fft_vals)
    return geo_mean / arith_mean


def is_bird_sound(audio_array):
    """
    Determine whether the given audio signal is likely a bird sound,
    based on spectral flatness.

    Args:
        audio_array (np.ndarray): The audio signal to analyze.

    Returns:
        bool: True if it's likely a tonal bird sound, False otherwise.
    """
    sfm = spectral_flatness(audio_array)
    print(f"Spectral Flatness: {sfm:.3f}")

    return sfm < 0.56  # Threshold can be adjusted experimentally


async def handle_client(websocket):
    """
    Handle communication with a single WebSocket client.
    Receives audio data in chunks and processes it upon receiving "END".

    Args:
        websocket (websockets.WebSocketServerProtocol): The connected client socket.
    """
    client_ip = websocket.remote_address[0]
    client_id = client_ip  # Default ID until set
    client_buffers[client_ip] = bytearray()

    print(f"Client connected: {client_ip}")

    try:
        async for message in websocket:
            if isinstance(message, str):
                # Handle text messages (used for client identification or control signals)
                if message.startswith("ID:"):
                    # Set or update client ID
                    client_id = message[3:].strip()
                    client_ids[client_ip] = client_id
                    print(f"Client {client_ip} set ID: {client_id}")
                    # Move buffer to new ID
                    client_buffers[client_id] = client_buffers.pop(client_ip, bytearray())
                elif message == "END":
                    # Finished receiving audio — process and save if valid
                    if client_id in client_buffers:
                        print(f"Received data from client {client_id}.")

                        audio_array = np.frombuffer(client_buffers[client_id], dtype=np.int16)

                        if not is_bird_sound(audio_array):
                            print(f"Skipped saving: not tonal (likely noise).")
                            client_buffers[client_id] = bytearray()
                            continue

                        # Save audio with timestamped filename
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        folder = f"recordings/{client_id}"
                        os.makedirs(folder, exist_ok=True)

                        filename = f"{folder}/recording_{timestamp}.flac"
                        sf.write(filename, audio_array, samplerate=SAMPLE_RATE, format="FLAC")
                        print(f"Saved: {filename}")

                        client_buffers[client_id] = bytearray()
                else:
                    print(f"Text message from {client_ip}: {message}")

            elif isinstance(message, bytes):
                # Receive binary audio data and append to buffer
                if client_id in client_buffers:
                    client_buffers[client_id].extend(message)
                else:
                    client_buffers[client_id] = bytearray(message)

    except websockets.ConnectionClosed:
        print(f"Client {client_ip} disconnected")
        # Clean up buffers and IDs on disconnect
        if client_id in client_buffers:
            del client_buffers[client_id]
        if client_ip in client_ids:
            del client_ids[client_ip]


async def main():
    """
    Start the WebSocket server and listen for incoming audio streams.
    """
    print("Waiting for audio stream on ws://0.0.0.0:8765")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()  # Keep running forever


if __name__ == "__main__":
    # Run the WebSocket server
    asyncio.run(main())
