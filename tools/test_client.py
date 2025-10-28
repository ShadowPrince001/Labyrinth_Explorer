import time
import socketio  # type: ignore

s = socketio.Client()

@s.event
def connect():
    print('connected')
    s.emit('start')

@s.on('output')
def on_output(data):
    text = data.get('text') if isinstance(data, dict) else data
    print('OUT:', text.strip())

@s.event
def disconnect():
    print('disconnected')

if __name__ == '__main__':
    try:
        s.connect('http://localhost:5000')
        # listen for 8 seconds
        for _ in range(8):
            time.sleep(1)
    except Exception as e:
        print('client error', e)
    finally:
        try:
            s.disconnect()
        except:
            pass
        print('done')
