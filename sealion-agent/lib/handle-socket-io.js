/* 
This module handles socketIO
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var io = require('socket.io-client');
var socketIoOptions = require('../etc/config/server-config.json').socketIODetails;
var logData = require('./log.js');

/** @constructor */
function HandleSocketIO( ) {
    this.attemptCount = 0;
    this.isReconnect = true;
};

// function to reconnect
HandleSocketIO.prototype.reconnect = function(self) {
    
    if(! self.socket) {
        self.createConnection();       
    } else if( ! self.socket.socket.connected) {
        var ssId = require('./global.js').sessionCookie;
        self.socket.socket.disconnect();
        self.socket.socket.setCookie({'cookies':ssId});
        self.socket.socket.connect();
    }
} 

// function to attempt reconnection in case multiple attempts failed
/*
Here we need to attempt reconnecting till program lasts.
If max connection attempts are less than length of array supplied then use time interval of last index element
otherwise use the index period for the same
*/
HandleSocketIO.prototype.attemptReconnect = function(self) {
    
    if(self.attemptCount >= socketIoOptions.reconnectInterval.length) {
        setTimeout(self.reconnect, 
            socketIoOptions.reconnectInterval[socketIoOptions.reconnectInterval.length - 1] * 1000, 
            self);
    } else {
        setTimeout(self.reconnect, 
            socketIoOptions.reconnectInterval[self.attemptCount] * 1000, 
            self);
        self.attemptCount++;
    }
}

// creates new socketIO connection
HandleSocketIO.prototype.createConnection = function() {
    var tempThis = this;
    var ssId = require('./global.js').sessionCookie;
    
    if(! this.socket) {
    
        var onConnect = function() {
            logData("Socket IO connected");
        }
    
        var onError = function(error) {
            logData("Error in Socket.io connection " + error);
            if(tempThis.isReconnect) {
                tempThis.attemptReconnect(tempThis);
            }
        }
    
        var onUnhandledException = function(error) {
            logData('Socket.io Caught unhandled exception');
            if(tempThis.isReconnect) {
                tempThis.attemptReconnect(tempThis);
            }
        }
    
        var onMsg = function(msg) {
            logData(msg);
        }   
        
        var onDisconnect = function() {
            logData("Socket.io Connection disconnected");
            if(tempThis.isReconnect) {
                tempThis.attemptReconnect(tempThis);
            }
        } 
        
        this.socket = io.connect(socketIoOptions.url, {'cookies':ssId});
        this.socket.on('connect', onConnect);
        this.socket.on('error', onError);
        this.socket.on('unhandledException', onUnhandledException);
        this.socket.on('msg', onMsg);
        this.socket.on('disconnect', onDisconnect);
    } else {
        if(this.socket.socket.connected) {
           this.socket.socket.disconnect();
        }
        this.socket.socket.setCookie({'cookies':ssId});
        this.socket.socket.connect();
    }
    
    this.isReconnect = true;
    this.attemptCount = 0;
}

// closes socketIO connection
HandleSocketIO.prototype.closeConnection = function( ) {
    this.isReconnect = false;
    if(this.socket.socket.connected) {
        this.socket.socket.disconnect();
    }
}

module.exports = HandleSocketIO;
