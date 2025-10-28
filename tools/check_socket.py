import socketio
import time

s = socketio.Client(logger=True)

@s.event
def connect():
    print('connected')

@s.event
def connect_error(data):
    print('connect_error', data)

@s.event
def disconnect():
    print('disconnected')

try:
    s.connect('http://127.0.0.1:5000', transports=['websocket','polling'])
    time.sleep(1)
    s.emit('start')
    time.sleep(1)
except Exception as e:
    print('exception', e)
finally:
    try:
        s.disconnect()
    except Exception:
        pass
