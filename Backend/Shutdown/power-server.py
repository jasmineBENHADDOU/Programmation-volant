import asyncio 
import os
import websockets

HOST = "0.0.0.0"
PORT = 8765

async def handle_client(websocket):
    print("Client connecté")

    try:
        async for message in websocket:
            print(f"Message reçu : {message}")

            if message == "ping":
                await websocket.send("pong")

            elif message == "poweroff":
                await websocket.send("shutdown_requested")
                # Décommente cette ligne quand le test fonctionne
                # os.system("sudo shutdown now")
                os.system("sudo /sbin/shutdown now")

            else:
                await websocket.send("unknown_command")

    except websockets.ConnectionClosed:
        print("Client déconnecté")

async def main():
    print(f"WebSocket server running on ws://{HOST}:{PORT}")
    
    async with websockets.serve(handle_client, HOST, PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
