import os
import asyncio
import websockets
import soundfile as sf
import numpy as np
from datetime import datetime
from scipy.fft import rfft

SAMPLE_RATE = 16000

client_buffers = {}
client_ids = {}

# คำนวณ spectral flatness
def spectral_flatness(audio_array):
    samples = audio_array.astype(np.float32)
    fft_vals = np.abs(rfft(samples)) + 1e-10  # ป้องกัน log(0)
    geo_mean = np.exp(np.mean(np.log(fft_vals)))
    arith_mean = np.mean(fft_vals)
    return geo_mean / arith_mean

# ใช้แค่ flatness ในการตัดสินใจ
def is_bird_sound(audio_array):
    sfm = spectral_flatness(audio_array)
    print(f"Spectral Flatness: {sfm:.3f}")

    # flatness ต่ำ → เป็นเสียง tonal เช่น เสียงนก
    return sfm < 0.56  # ปรับ threshold ตามสภาพแวดล้อมได้

async def handle_client(websocket):
    client_ip = websocket.remote_address[0]
    client_id = client_ip
    client_buffers[client_ip] = bytearray()

    print(f"Client connected: {client_ip}")

    try:
        async for message in websocket:
            if isinstance(message, str):
                if message.startswith("ID:"):
                    client_id = message[3:].strip()
                    client_ids[client_ip] = client_id
                    print(f"Client {client_ip} set ID: {client_id}")
                    client_buffers[client_id] = client_buffers.pop(client_ip, bytearray())
                elif message == "END":
                    if client_id in client_buffers:
                        print(f"📥 Received data from client {client_id}.")

                        audio_array = np.frombuffer(client_buffers[client_id], dtype=np.int16)

                        if not is_bird_sound(audio_array):
                            print(f"Skipped saving: not tonal (likely noise).")
                            client_buffers[client_id] = bytearray()
                            continue

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
                if client_id in client_buffers:
                    client_buffers[client_id].extend(message)
                else:
                    client_buffers[client_id] = bytearray(message)

    except websockets.ConnectionClosed:
        print(f"Client {client_ip} disconnected")
        if client_id in client_buffers:
            del client_buffers[client_id]
        if client_ip in client_ids:
            del client_ids[client_ip]

async def main():
    print("Waiting for audio stream on ws://0.0.0.0:8765")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())

