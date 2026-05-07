from pythonosc import dispatcher, osc_server

def handle(address, *args):
    print(f"Received: {address} → {args}")

d = dispatcher.Dispatcher()
d.map("/motionsketch/prediction", handle)

server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 9000), d)
print("Listening on port 9000...")
server.serve_forever()