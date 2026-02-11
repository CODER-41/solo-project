"""WebSocket events"""
def register_socket_events(socketio):
    """Register all socket events"""
    
    @socketio.on('connect')
    def handle_connect():
        print('Client connected')
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print('Client disconnected')
