var io = require('socket.io-client');
var socketIoOptions = require('../etc/config/socket-io-config.js');

var Sealion = { };

Sealion.HandleSocketIO = function ( ) {
};

Sealion.HandleSocketIO.prototype.attemptReconnect = function() {
    if(! this.socket) {
        this.createConnection();       
    } else if( ! this.socket.socket.connected) {
        this.socket.disconnect();
        this.socket.socket.connect();
    }
}


Sealion.HandleSocketIO.prototype.createConnection = function( ) {
    var tempThis = this;
    
    this.socket = io.connect(socketIoOptions.host/*, socketIoOptions.options*/);
    
    this.socket.on('connect', function() {
        console.log("Socket IO connected");
    });
    
    this.socket.on('update', function(msg) {
        // update operation will go here
    
        console.log('Got message ' + JSON.stringify(msg));
    });

    this.socket.on('error', function(error) {
        console.log("Error in Socket.io connection");
    });
    
    this.socket.on('unhandledException', function(error) {
        console.log('Socket.io Caught unhandled exception');
    });
    
    this.socket.on('disconnect', function(){
        console.log("Socket.io Connection disconnected");
    });
}

Sealion.HandleSocketIO.prototype.closeConnection = function( ) {
    console.log("SocketIO: closing connection");
    this.socket.disconnect();
}

module.exports = Sealion.HandleSocketIO; 
