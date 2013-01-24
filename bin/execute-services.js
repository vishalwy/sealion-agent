var services = require('../etc/config/services-config.js');
var ExecuteCommand = require('./execute-command.js');
var Sqlite3 = require('./sqlite-wrapper.js');
var SocketIo = require('./handle-socket-io.js');

var Sealion = { };
Sealion.DEFAULT_INTERVAL = 300000;

var sqliteObj = new Sqlite3();
var socketObj = new SocketIo();

Sealion.onExecuteTrigger = function(serviceDetails) { 
    var ec = new ExecuteCommand(sqliteObj);
    ec.executeCommand(serviceDetails.command, { });
}

Sealion.interId = [];

var startServices = function() {
    console.log("starting services");
    for(var counter in services) {
        if(services[counter]['name'] && services[counter]['command']) {
            console.log("starting service for " + services[counter]['name']);
            
            Sealion.interId.push(
                setInterval(
                    Sealion.onExecuteTrigger, 
                    services[counter]['interval'] ? services[counter]['interval'] * 1000 : Sealion.DEFAULT_INTERVAL, 
                    services[counter]
                )
            );
        }
    }
    
    // check if socket.io is connected or not
    Sealion.interId.push(
        setInterval(
            checkConnection,
            216000000)
        );
}

var checkConnection = function() {
    socketObj.attemptReconnect();
}

var stopServices = function() {
    console.log("Stopping Services");
    for(var counter in Sealion.interId) {
        clearInterval(Sealion.interId[counter]);
    }
    sqliteObj.closeDb();
    socketObj.closeConnection();
}

var startListeningSocketIO = function() {
    socketObj.createConnection(); 
}

var closeSocketIO = function() {
    socketObj.closeConnection();
}

exports.startServices = startServices;
exports.stopServices = stopServices;
exports.startListeningSocketIO = startListeningSocketIO;
exports.closeSocketIO = closeSocketIO;
