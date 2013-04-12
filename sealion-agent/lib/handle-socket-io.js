/* 
This module handles socketIO
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var io = require('socket.io-client');
var logData = require('./log.js');
var socketIoOptions = require('../etc/config/server-config.json').socketIODetails;
/** @constructor */
function HandleSocketIO( ) {

};

// creates new socketIO connection
HandleSocketIO.prototype.createConnection = function() {
    var tempThis = this;
    
    
    if(! this.socket) {
    
        var onConnect = function() {
            logData("Socket IO connected");
        }
    
        var onError = function(error) {
            logData("Error in Socket.io connection " + error);
        }
    
        var onUnhandledException = function(error) {
            logData('Socket.io Caught unhandled exception');
        }
    
        var onMsg = function(msg) {
            logData(msg);
        }   
        
        var onDisconnect = function() {
            logData("Socket.io Connection disconnected");
        } 
        
        this.socket = io.connect(socketIoOptions.url);
        this.socket.on('connect', onConnect);
        this.socket.on('error', onError);
        this.socket.on('unhandledException', onUnhandledException);
        this.socket.on('msg', onMsg);
        this.socket.on('disconnect', onDisconnect);
    } else {
        if(this.socket.socket.connected) {
           this.socket.socket.disconnectSync();
        }
        this.socket.socket.connect();
    }
}

// closes socketIO connection
HandleSocketIO.prototype.closeConnection = function( ) {
    
    if(this.socket && this.socket.socket.connected) {
        this.socket.socket.disconnectSync();
    }
}

module.exports = HandleSocketIO;
