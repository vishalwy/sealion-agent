var io = require('socket.io-client');
var socketIoOptions = require('../etc/config/server-config.json').socketIODetails;

var Sealion = { };

Sealion.HandleSocketIO = function ( ) {
    this.attemptCount = 0;
    this.isReconnect = true;
};

Sealion.HandleSocketIO.prototype.reconnect = function(cookieData, self) {
    if(! self.socket) {
        self.createConnection(cookieData);       
    } else if( ! self.socket.socket.connected) {
        self.socket.disconnect();
        self.socket.socket.connect();
    }
} 

Sealion.HandleSocketIO.prototype.attemptReconnect = function(cookieData, self) {
    
    if(self.attemptCount >= socketIoOptions.reconnectInterval.length) {
        setTimeout(self.reconnect, 
            socketIoOptions.reconnectInterval[socketIoOptions.reconnectInterval.length - 1] * 1000, 
            cookieData, self);
    } else {
        setTimeout(self.reconnect, 
            socketIoOptions.reconnectInterval[self.attemptCount] * 1000, 
            cookieData, self);
        self.attemptCount++;
    }
}

Sealion.HandleSocketIO.prototype.createConnection = function(cookieData) {
    var tempThis = this;
    this.socket = io.connect(socketIoOptions.url, {'cookies':cookieData});
    this.isReconnect = true;
    this.attemptCount = 0;
    
    this.socket.on('connect', function() {
        console.log("Socket IO connected");
    });
    
    this.socket.on('error', function(error) {
        console.log("Error in Socket.io connection" + error);
        if(tempThis.isReconnect) {
            tempThis.attemptReconnect(cookieData, tempThis);
        }
    });
    
    this.socket.on('unhandledException', function(error) {
        console.log('Socket.io Caught unhandled exception');
        if(tempThis.isReconnect) {
            tempThis.attemptReconnect(cookieData, tempThis);
        }
    });
    
    this.socket.on('msg', function(msg) {
        console.log(msg);
    });
    
    this.socket.on('disconnect', function(){
        console.log("Socket.io Connection disconnected");
        if(tempThis.isReconnect) {
            tempThis.attemptReconnect(cookieData, tempThis);
        }
    });
}

Sealion.HandleSocketIO.prototype.closeConnection = function( ) {
    this.isReconnect = false;
    console.log("SocketIO: closing connection");
    this.socket.disconnect();
}

module.exports = Sealion.HandleSocketIO; 
