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
        self.socket.socket.disconnect();
        self.socket.socket.setCookie({'cookies':cookieData});
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
    
    if(! this.socket) {
    
        var onConnect = function() {
            console.log("Socket IO connected");
        }
    
        var onError = function(error) {
            console.log("Error in Socket.io connection " + error);
            if(tempThis.isReconnect) {
                tempThis.attemptReconnect(cookieData, tempThis);
            }
        }
    
        var onUnhandledException = function(error) {
            console.log('Socket.io Caught unhandled exception');
            if(tempThis.isReconnect) {
                tempThis.attemptReconnect(cookieData, tempThis);
            }
        }
    
        var onMsg = function(msg) {
            console.log(msg);
        }   
        
        var onDisconnect = function() {
            console.log("Socket.io Connection disconnected");
            if(tempThis.isReconnect) {
                tempThis.attemptReconnect(cookieData, tempThis);
            }
        } 
        
        this.socket = io.connect(socketIoOptions.url, {'cookies':cookieData});
        this.socket.on('connect', onConnect);
        this.socket.on('error', onError);
        this.socket.on('unhandledException', onUnhandledException);
        this.socket.on('msg', onMsg);
        this.socket.on('disconnect', onDisconnect);
    } else {
        this.socket.socket.disconnect();
        this.socket.socket.setCookie({'cookies':cookieData});
        this.socket.socket.connect();
    }
    
    this.isReconnect = true;
    this.attemptCount = 0;
}

Sealion.HandleSocketIO.prototype.closeConnection = function( ) {
    this.isReconnect = false;
    this.socket.socket.disconnect();
}

module.exports = Sealion.HandleSocketIO; 
